#!/usr/bin/env bash
# MediaCrawler macOS arm64 单文件构建脚本
#
# 前置条件：
#   1. 激活的 Python 3.11+ 虚拟环境，且已安装项目依赖与 nuitka
#   2. ccache（brew install ccache，可选但强烈建议，显著加速增量构建）
#
# 用法：
#   ./scripts/build-macos-arm64.sh              # 使用当前 python
#   MC_PYTHON=./.venv/bin/python ./scripts/build-macos-arm64.sh
#   MC_VERSION=0.2.0+mc20261001 ./scripts/build-macos-arm64.sh
set -euo pipefail

cd "$(dirname "$0")/.."

VERSION="${MC_VERSION:-0.1.0+mc$(date +%Y%m%d)}"
PY="${MC_PYTHON:-python3}"

echo "==> 版本: ${VERSION}"

if ! "${PY}" -c "import nuitka" >/dev/null 2>&1; then
    echo "错误: 当前 Python 未安装 nuitka，先执行: ${PY} -m pip install nuitka" >&2
    exit 1
fi

if ! command -v ccache >/dev/null 2>&1; then
    echo "提示: 未检测到 ccache（brew install ccache 可显著加速增量构建），继续构建..." >&2
fi

mkdir -p build

# 说明：
# - --onefile-tempdir-spec 必须显式指定为静态路径，否则每次运行都会解压+删除（无缓存）
# - {VERSION} 来自 --product-version，发新版自动换目录并重新解压
# - --playwright-include-browser=none：CDP 模式用本机 Chrome，绝不内嵌浏览器
"${PY}" -m nuitka \
    --onefile \
    --enable-plugin=playwright \
    --playwright-include-browser=none \
    --include-data-files=libs/douyin.js=libs/douyin.js \
    --include-data-files=libs/zhihu.js=libs/zhihu.js \
    --include-data-files=libs/stealth.min.js=libs/stealth.min.js \
    --include-data-dir=media_platform/kuaishou/graphql=media_platform/kuaishou/graphql \
    --include-data-files=docs/hit_stopwords.txt=docs/hit_stopwords.txt \
    --include-data-files=docs/STZHONGS.TTF=docs/STZHONGS.TTF \
    --include-data-files=LICENSE=LICENSE \
    --onefile-tempdir-spec="{CACHE_DIR}/{PRODUCT}/{VERSION}" \
    --product-name=mediacrawler \
    --company-name=MarcusYuan \
    --product-version="${VERSION}" \
    --output-filename=mediacrawler \
    --output-dir=build \
    --report=build/report.xml \
    --assume-yes-for-downloads \
    main.py

echo "==> 构建完成:"
ls -lh build/mediacrawler
echo "==> 提示: macOS 可能拦截未签名二进制，首次运行前执行: xattr -c build/mediacrawler"
