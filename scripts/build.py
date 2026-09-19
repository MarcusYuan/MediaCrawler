#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MediaCrawler 跨平台 Nuitka 构建脚本。

用法：
    python scripts/build.py             # 正式构建（当前平台）
    python scripts/build.py --dry-run   # 只打印 nuitka 命令，不执行（本地/CI 校验）

版本号单一事实源：tools/box_contract.APP_VERSION。
产物：build/mediacrawler[.exe]（onefile 单文件）。
"""
import argparse
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# macOS 部署目标：扩大兼容面（跟随构建机 SDK 会得到过高的系统要求）
MACOS_DEPLOYMENT_TARGET = "12.0"


def resolve_app_version() -> str:
    sys.path.insert(0, REPO_ROOT)
    from tools.box_contract import APP_VERSION  # noqa: E402

    return APP_VERSION


def build_command(python: str, version: str) -> list:
    exe_name = "mediacrawler.exe" if os.name == "nt" else "mediacrawler"
    return [
        python, "-m", "nuitka",
        "--onefile",
        "--enable-plugin=playwright",
        "--playwright-include-browser=none",
        "--include-data-files=libs/douyin.js=libs/douyin.js",
        "--include-data-files=libs/zhihu.js=libs/zhihu.js",
        "--include-data-files=libs/stealth.min.js=libs/stealth.min.js",
        "--include-data-dir=media_platform/kuaishou/graphql=media_platform/kuaishou/graphql",
        "--include-data-files=docs/hit_stopwords.txt=docs/hit_stopwords.txt",
        "--include-data-files=docs/STZHONGS.TTF=docs/STZHONGS.TTF",
        "--include-data-files=LICENSE=LICENSE",
        "--include-package-data=wordcloud",
        "--include-package-data=jieba",
        # 必须显式静态路径：默认规格每次运行解压后删除（无缓存）
        "--onefile-tempdir-spec={CACHE_DIR}/{PRODUCT}/{VERSION}",
        "--product-name=mediacrawler",
        "--company-name=MarcusYuan",
        f"--product-version={version}",
        f"--output-filename={exe_name}",
        "--output-dir=build",
        "--report=build/report.xml",
        "--assume-yes-for-downloads",
        "main.py",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只打印命令不执行")
    parser.add_argument("--python", default=sys.executable, help="用于运行 nuitka 的解释器")
    parser.add_argument("--version", default=None, help="覆盖版本号（默认取 box_contract.APP_VERSION）")
    args = parser.parse_args()

    version = args.version or resolve_app_version()
    cmd = build_command(args.python, version)

    print(f"==> 版本: {version} / 平台: {sys.platform}")
    print("==> " + " ".join(cmd))

    if args.dry_run:
        return 0

    import importlib.util

    if importlib.util.find_spec("nuitka") is None:
        print(f"错误: 未安装 nuitka，先执行: {args.python} -m pip install nuitka", file=sys.stderr)
        return 1

    env = os.environ.copy()
    if sys.platform == "darwin":
        env["MACOSX_DEPLOYMENT_TARGET"] = MACOS_DEPLOYMENT_TARGET
        print(f"==> MACOSX_DEPLOYMENT_TARGET={MACOS_DEPLOYMENT_TARGET}")

    os.makedirs(os.path.join(REPO_ROOT, "build"), exist_ok=True)
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=env)
    if result.returncode != 0:
        return result.returncode

    exe_name = "mediacrawler.exe" if os.name == "nt" else "mediacrawler"
    artifact = os.path.join(REPO_ROOT, "build", exe_name)
    size_mb = os.path.getsize(artifact) / 1024 / 1024
    print(f"==> 构建完成: build/{exe_name} ({size_mb:.0f}MB)")
    if sys.platform == "darwin":
        print("==> 提示: macOS 可能拦截未签名二进制，首次运行前执行: xattr -c build/mediacrawler")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
