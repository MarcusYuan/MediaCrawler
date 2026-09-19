#!/usr/bin/env bash
# 本地便捷入口：实际构建逻辑在 scripts/build.py（跨平台单一实现）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -n "${MC_PYTHON:-}" ]; then
    PY="${MC_PYTHON}"
elif [ -x ".venv/bin/python" ]; then
    PY="./.venv/bin/python"
else
    PY="python3"
fi

exec "${PY}" scripts/build.py "$@"
