# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/app_paths.py
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

"""双模式路径解析。

源码模式（python main.py）：行为与历史版本一致，仓库内资源从仓库根解析，
数据写入跟随当前工作目录。

打包模式（Nuitka onefile）：只读资源从解压目录解析；可写数据统一落到
~/.mediacrawler，避免写进随版本变化的解压缓存目录。

注意：本模块只依赖标准库，不得 import 项目内其他模块——它会被
main.py 顶部和 config/ 引用，必须保持零项目依赖。
"""

import os
import sys


def is_frozen() -> bool:
    """是否运行在 Nuitka 打包产物中。"""
    return hasattr(sys.modules.get("__main__"), "__compiled__")


def get_resource_root() -> str:
    """只读资源根目录：源码模式为仓库根，打包模式为 onefile 解压目录。

    Nuitka 编译模块的 __file__ 在运行时指向解压目录内的实际位置，
    因此两种模式统一用本文件（<根>/tools/app_paths.py）上溯两级求根。
    注意不能用 __compiled__.containing_dir——它指向可执行文件所在目录，
    onefile 下那里并没有打包进去的资源。
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_resource(rel_path: str) -> str:
    """把仓库内相对路径解析为绝对路径；绝对路径原样返回。"""
    if os.path.isabs(rel_path):
        return rel_path
    return os.path.join(get_resource_root(), rel_path)


def get_writable_root() -> str:
    """可写数据根目录：源码模式为当前工作目录（与历史行为一致），
    打包模式为 ~/.mediacrawler。"""
    if is_frozen():
        return os.path.expanduser("~/.mediacrawler")
    return os.getcwd()
