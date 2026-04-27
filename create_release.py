"""一键发布脚本 - 需要设置GitHub Token"""
import os, sys, json, urllib.request, urllib.error

def create_release(token):
    url = 'https://api.github.com/repos/yahooor/air_quality_cn/releases'
    data = {
        "tag_name": "v2.3.2",
        "name": "v2.3.2",
        "body": "v2.3.2 - 优化中国数据覆盖sitemap入口\n- 中国AQI数据覆盖率提升至99.7%\n\n### 更新内容\n- sitemap入口支持更稳定的AQI数据获取\n- 中国地点AQI覆盖率99.7%",
        "draft": False,
        "prerelease": False,
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.github+json'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get('html_url')
    except urllib.error.HTTPError as e:
        error = json.loads(e.read().decode())
        return False, error.get('message')

if __name__ == '__main__':
    # 方式1: 从环境变量读取
    token = os.environ.get('GH_TOKEN')
    if not token:
        # 方式2: 从参数传入
        token = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not token:
        print("用法:")
        print("  set GH_TOKEN=your_github_token && python create_release.py")
        print("  或: python create_release.py your_github_token")
        print()
        print("获取Token: GitHub Settings → Developer settings → Personal access tokens")
        exit(1)
    
    success, msg = create_release(token)
    if success:
        print(f"✅ Release创建成功: {msg}")
    else:
        print(f"❌ 失败: {msg}")