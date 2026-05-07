#!/usr/bin/env python3
"""
release.py — air_quality_cn 一键发布脚本

用法:
    python release.py <版本号> "<更新日志>"
    python release.py 2.7.0 "新增紫外线预警功能"

功能:
    1. Preflight 检查（工作区干净、远程 tag 不重复、Token 获取）
    2. 更新 manifest.json 版本号
    3. 通过 Git Data API 提交所有变更（绕过 git push 网络问题）
    4. 创建 Git Tag
    5. 创建 GitHub Release
    6. 同步本地 git

纯标准库，零外部依赖。
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ─── 配置 ────────────────────────────────────────────────────────
OWNER = "yahooor"
REPO = "air_quality_cn"
BRANCH = "main"
MANIFEST_PATH = "custom_components/air_quality_cn/manifest.json"
README_PATH = "README.md"
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # 指数退避（秒）

# ─── 颜色输出 ────────────────────────────────────────────────────
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}

NO_COLOR = not sys.stdout.isatty()


def _c(color, text):
    if NO_COLOR:
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def info(msg):
    print(f"  {_c('cyan', 'ℹ')} {msg}")


def ok(msg):
    print(f"  {_c('green', '✓')} {msg}")


def warn(msg):
    print(f"  {_c('yellow', '⚠')} {msg}")


def fail(msg):
    print(f"  {_c('red', '✗')} {msg}")


def header(msg):
    print(f"\n{_c('bold', f'━━━ {msg} ━━━')}")


# ─── HTTP 工具 ───────────────────────────────────────────────────
def api_request(url, method="GET", data=None, token=None, retries=MAX_RETRIES):
    """带重试的 GitHub API 请求"""
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method)
        req.add_header("Accept", "application/vnd.github.v3+json")
        if token:
            req.add_header("Authorization", f"token {token}")
        if data is not None:
            req.data = json.dumps(data).encode()
            req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()[:500]
            if attempt < retries - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                warn(f"HTTP {e.code}，{delay}s 后重试 ({attempt+1}/{retries})")
                time.sleep(delay)
                continue
            fail(f"HTTP {e.code}: {err_body}")
            return None
        except (urllib.error.URLError, OSError) as e:
            if attempt < retries - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                warn(f"网络错误: {e}，{delay}s 后重试 ({attempt+1}/{retries})")
                time.sleep(delay)
                continue
            fail(f"网络错误: {e}")
            return None
    return None


# ─── Token 获取 ──────────────────────────────────────────────────
def get_token():
    """获取 GitHub Token（优先级：credential helper > remote URL > 环境变量）"""
    # Method 1: git credential fill
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.split("\n"):
            if line.startswith("password="):
                token = line.split("=", 1)[1]
                if token:
                    return token
    except Exception:
        pass

    # Method 2: 从 remote URL 提取
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        url = result.stdout.strip()
        # 格式: https://user:token@github.com/owner/repo.git
        match = re.search(r"://[^:]*:([^@]+)@", url)
        if match:
            return match.group(1)
    except Exception:
        pass

    # Method 3: 环境变量
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        return token

    return None


# ─── Preflight 检查 ──────────────────────────────────────────────
def check_git_clean():
    """检查工作区是否干净"""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, timeout=5,
    )
    if result.stdout.strip():
        fail("工作区不干净，请先提交或暂存变更:")
        print(result.stdout.strip())
        return False
    return True


def check_remote_tag(tag_name, token):
    """检查远程是否已存在同名 tag"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/git/ref/tags/{tag_name}"
    result = api_request(url, token=token, retries=1)
    if result is not None:
        fail(f"远程已存在 tag: {tag_name}")
        return False
    # 404 = tag 不存在，是期望的结果
    return True


def check_remote_release(tag_name, token):
    """检查远程是否已存在同名 Release"""
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/tags/{tag_name}"
    result = api_request(url, token=token, retries=1)
    if result is not None:
        fail(f"远程已存在 Release: {tag_name}")
        return False
    return True


# ─── 版本号操作 ──────────────────────────────────────────────────
def read_current_version():
    """从 manifest.json 读取当前版本号"""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    return manifest.get("version", "unknown")


def update_manifest(new_version):
    """更新 manifest.json 中的版本号"""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    old_version_match = re.search(r'"version"\s*:\s*"([^"]+)"', content)
    if not old_version_match:
        fail("manifest.json 中未找到 version 字段")
        return False

    old_version = old_version_match.group(1)
    new_content = content.replace(f'"version": "{old_version}"', f'"version": "{new_version}"')

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    ok(f"manifest.json: {old_version} → {new_version}")
    return True


# ─── Git Data API 提交 ───────────────────────────────────────────
def get_changed_files():
    """获取所有已修改/新增的文件路径"""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, timeout=5,
    )
    changed = result.stdout.strip().split("\n") if result.stdout.strip() else []

    # 也检查暂存区
    result2 = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, timeout=5,
    )
    staged = result2.stdout.strip().split("\n") if result2.stdout.strip() else []

    # 检查未跟踪的文件
    result3 = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, timeout=5,
    )
    untracked = result3.stdout.strip().split("\n") if result3.stdout.strip() else []

    all_files = list(set(changed + staged + untracked))
    return [f for f in all_files if f]  # 过滤空字符串


def git_commit_via_api(token, version, commit_message):
    """通过 Git Data API 提交所有变更文件（单次 commit）"""
    header("Git Data API 提交")

    # 获取 main 分支当前 commit SHA
    info("获取 main 分支 HEAD...")
    ref = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}",
        token=token,
    )
    if not ref:
        fail("无法获取 main 分支引用")
        return None
    head_sha = ref["object"]["sha"]
    ok(f"HEAD: {head_sha[:8]}")

    # 获取 HEAD commit 的 tree SHA
    head_commit = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/commits/{head_sha}",
        token=token,
    )
    if not head_commit:
        fail("无法获取 HEAD commit")
        return None
    base_tree_sha = head_commit["tree"]["sha"]

    # 获取变更文件列表
    changed_files = get_changed_files()
    if not changed_files:
        warn("没有检测到本地变更文件，仅更新 manifest.json")
        changed_files = [MANIFEST_PATH]

    info(f"变更文件: {', '.join(changed_files)}")

    # 为每个文件创建 blob
    tree_items = []
    for filepath in changed_files:
        if not os.path.exists(filepath):
            warn(f"文件不存在，跳过: {filepath}")
            continue

        with open(filepath, "rb") as f:
            file_content = f.read()

        info(f"创建 blob: {filepath} ({len(file_content)} bytes)")
        blob = api_request(
            f"https://api.github.com/repos/{OWNER}/{REPO}/git/blobs",
            method="POST",
            data={
                "content": base64.b64encode(file_content).decode(),
                "encoding": "base64",
            },
            token=token,
        )
        if not blob:
            fail(f"创建 blob 失败: {filepath}")
            return None
        tree_items.append({
            "path": filepath,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    if not tree_items:
        fail("没有文件需要提交")
        return None

    # 创建 tree
    info("创建 tree...")
    tree = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/trees",
        method="POST",
        data={
            "base_tree": base_tree_sha,
            "tree": tree_items,
        },
        token=token,
    )
    if not tree:
        fail("创建 tree 失败")
        return None
    ok(f"Tree: {tree['sha'][:8]}")

    # 创建 commit
    info("创建 commit...")
    commit = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/commits",
        method="POST",
        data={
            "message": commit_message,
            "tree": tree["sha"],
            "parents": [head_sha],
        },
        token=token,
    )
    if not commit:
        fail("创建 commit 失败")
        return None
    commit_sha = commit["sha"]
    ok(f"Commit: {commit_sha[:8]}")

    # 更新 main 分支引用
    info("更新 main 分支引用...")
    update = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH}",
        method="PATCH",
        data={"sha": commit_sha, "force": False},
        token=token,
    )
    if not update:
        fail(f"更新分支引用失败。Commit 已创建: {commit_sha}")
        print(f"\n  恢复建议: 手动更新分支引用:")
        print(f'  curl -X PATCH -H "Authorization: token <TOKEN>" \\')
        print(f'    https://api.github.com/repos/{OWNER}/{REPO}/git/refs/heads/{BRANCH} \\')
        print(f'    -d \'{{"sha": "{commit_sha}"}}\'')
        return None
    ok(f"main → {commit_sha[:8]}")

    return commit_sha


# ─── Tag & Release ───────────────────────────────────────────────
def create_tag(commit_sha, tag_name, token):
    """创建轻量 tag"""
    header("创建 Tag")
    info(f"创建 tag {tag_name} → {commit_sha[:8]}")

    result = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/git/refs",
        method="POST",
        data={
            "ref": f"refs/tags/{tag_name}",
            "sha": commit_sha,
        },
        token=token,
    )
    if not result:
        fail(f"创建 tag 失败。Commit 已推送: {commit_sha}")
        print(f"\n  恢复建议: 手动创建 tag:")
        print(f'  curl -X POST -H "Authorization: token <TOKEN>" \\')
        print(f'    https://api.github.com/repos/{OWNER}/{REPO}/git/refs \\')
        print(f'    -d \'{{"ref": "refs/tags/{tag_name}", "sha": "{commit_sha}"}}\'')
        return False
    ok(f"Tag {tag_name} 创建成功")
    return True


def create_release(tag_name, version, changelog, token):
    """创建 GitHub Release"""
    header("创建 Release")

    release_body = f"## 更新\n\n{changelog}"
    result = api_request(
        f"https://api.github.com/repos/{OWNER}/{REPO}/releases",
        method="POST",
        data={
            "tag_name": tag_name,
            "target_commitish": BRANCH,
            "name": f"{tag_name} - {changelog}",
            "body": release_body,
            "draft": False,
            "prerelease": False,
        },
        token=token,
    )
    if not result:
        fail(f"创建 Release 失败。Tag 已创建: {tag_name}")
        print(f"\n  恢复建议: 手动创建 Release:")
        print(f'  打开 https://github.com/{OWNER}/{REPO}/releases/new?tag={tag_name}')
        return False

    ok(f"Release: {result['html_url']}")
    return True


# ─── 同步本地 ────────────────────────────────────────────────────
def sync_local(tag_name):
    """尝试同步本地 git 到远程状态"""
    header("同步本地")
    try:
        subprocess.run(["git", "fetch", "origin", BRANCH], timeout=30, check=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{BRANCH}"], timeout=5, check=True)
        ok(f"本地 main 已同步到远程")
    except Exception as e:
        warn(f"同步本地失败（不影响发布）: {e}")
        print(f"  稍后网络恢复后运行: git fetch origin && git reset --hard origin/main")


# ─── 主流程 ──────────────────────────────────────────────────────
def main():
    # 解析参数
    if len(sys.argv) < 3:
        print(f"用法: python {sys.argv[0]} <版本号> \"<更新日志>\"")
        print(f"示例: python {sys.argv[0]} 2.7.0 \"新增紫外线预警功能\"")
        sys.exit(1)

    version = sys.argv[1].lstrip("v")  # 去掉前缀 v
    changelog = sys.argv[2]
    tag_name = f"v{version}"
    commit_message = f"release: {tag_name} {changelog}"

    print(f"\n{'='*60}")
    print(f"  {_c('bold', 'air_quality_cn 发布脚本')}")
    print(f"  版本: {tag_name}")
    print(f"  日志: {changelog}")
    print(f"{'='*60}")

    # ── Stage 1: Preflight ──
    header("Preflight 检查")

    # Token
    info("获取 GitHub Token...")
    token = get_token()
    if not token:
        fail("无法获取 GitHub Token")
        print("  请确保 git credential 已配置，或设置 GITHUB_TOKEN 环境变量")
        sys.exit(1)
    ok(f"Token: {token[:8]}...{token[-4:]}")

    # 工作区
    info("检查工作区...")
    if not check_git_clean():
        sys.exit(1)
    ok("工作区干净")

    # 远程 tag
    info(f"检查远程 tag {tag_name}...")
    if not check_remote_tag(tag_name, token):
        sys.exit(1)
    ok(f"tag {tag_name} 不存在，可以创建")

    # 远程 Release
    info(f"检查远程 Release {tag_name}...")
    if not check_remote_release(tag_name, token):
        sys.exit(1)
    ok(f"Release {tag_name} 不存在，可以创建")

    # 当前版本
    current_version = read_current_version()
    info(f"当前版本: {current_version}")

    # ── Stage 2: 更新版本号 ──
    header("更新版本号")
    if not update_manifest(version):
        sys.exit(1)

    # ── Stage 3: Git Data API 提交 ──
    commit_sha = git_commit_via_api(token, version, commit_message)
    if not commit_sha:
        fail("提交失败，已中止")
        print(f"\n  已完成操作: manifest.json 已更新为 {version}")
        print(f"  恢复建议: git checkout -- {MANIFEST_PATH}")
        sys.exit(1)

    # ── Stage 4: 创建 Tag ──
    if not create_tag(commit_sha, tag_name, token):
        sys.exit(1)

    # ── Stage 5: 创建 Release ──
    if not create_release(tag_name, version, changelog, token):
        sys.exit(1)

    # ── Stage 6: 同步本地 ──
    sync_local(tag_name)

    # ── 完成 ──
    print(f"\n{'='*60}")
    print(f"  {_c('green', _c('bold', f'✓ {tag_name} 发布成功！'))}")
    print(f"  Release: https://github.com/{OWNER}/{REPO}/releases/tag/{tag_name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
