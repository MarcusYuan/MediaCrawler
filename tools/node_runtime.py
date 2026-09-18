# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/node_runtime.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

"""内嵌 Node 运行时注入。

pyexecjs 在 import execjs 时一次性扫描 PATH 并把探测结果永久缓存，
因此 ensure_embedded_node() 必须在任何触发 import execjs 的模块
（media_platform.douyin / media_platform.zhihu）之前调用，
目前由 main.py 顶部完成，调整 main.py 顶部 import 顺序时需保持该约束。
"""

import os

from tools.app_paths import is_frozen


def _driver_node_dir():
    """返回 playwright 自带 node 所在的 driver 目录，不存在则返回 None。"""
    try:
        import playwright
    except ImportError:
        return None

    driver_dir = os.path.join(
        os.path.dirname(os.path.abspath(playwright.__file__)), "driver"
    )
    candidates = ("node.exe", "node") if os.name == "nt" else ("node",)
    if any(os.path.isfile(os.path.join(driver_dir, name)) for name in candidates):
        return driver_dir
    return None


def ensure_embedded_node() -> None:
    """打包模式下把 playwright 自带的 node 前插进 PATH，供 pyexecjs 探测。

    源码模式不做任何事：继续使用系统 Node，保持原有行为。
    """
    if not is_frozen():
        return

    driver_dir = _driver_node_dir()
    if driver_dir is None:
        return

    path_env = os.environ.get("PATH", "")
    if path_env.startswith(driver_dir + os.pathsep):  # 幂等
        return
    os.environ["PATH"] = driver_dir + os.pathsep + path_env
