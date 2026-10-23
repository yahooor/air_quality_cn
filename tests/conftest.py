"""pytest 配置：将仓库根目录加入 sys.path 以导入 custom_components 包。"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
