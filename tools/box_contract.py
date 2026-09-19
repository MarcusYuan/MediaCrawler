# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/box_contract.py
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

"""Plugin Box 机器输出合同层（Box machine output contract v1）。

实现 plugin-box《Skill 与 CLI 合同》对 Managed CLI 的机器可读要求：

- stdout 只输出一个最终 JSON 文档（envelope），日志/进度全部走 stderr；
- 稳定错误码与退出码一一对应；
- doctor 零网络健康检查；
- 领域命令结果通过输出文件快照差分统计。

本模块不依赖 config（避免与 cmd_arg 的加载顺序耦合），平台相关常量就地定义。
"""

import json
import os
import shutil
import sys

from tools.app_paths import get_writable_root

APP_VERSION = "0.1.1"

SUPPORTED_PLATFORMS = ("xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu")

EXIT_CODES = {
    "internal_error": 1,
    "invalid_input": 2,
    "not_configured": 3,
    "auth_required": 4,
    "rate_limited": 5,
    "timeout": 6,
    "cancelled": 130,
}

MACHINE_MODE = False
_ENVELOPE_EMITTED = False


class BoxCliError(Exception):
    """携带稳定错误码的业务异常，由入口统一转成失败 envelope 与退出码。"""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def set_machine_mode(enabled: bool) -> None:
    global MACHINE_MODE
    MACHINE_MODE = enabled


def emit_line(message: str) -> None:
    """人类模式状态信息走 stdout（保持历史行为）；机器模式走 stderr。"""
    if MACHINE_MODE:
        print(message, file=sys.stderr)
    else:
        print(message)


def output_envelope(result=None, error: "BoxCliError | tuple | None" = None) -> None:
    """把唯一的最终 JSON 文档写到 stdout（§7.1 envelope），幂等保护防重复输出。"""
    global _ENVELOPE_EMITTED
    if _ENVELOPE_EMITTED:
        return
    _ENVELOPE_EMITTED = True

    if error is None:
        doc = {"contract_version": "1", "ok": True, "result": result or {}}
    else:
        if isinstance(error, BoxCliError):
            code, message, retryable = error.code, error.message, error.retryable
        else:
            code, message, retryable = error
        doc = {
            "contract_version": "1",
            "ok": False,
            "error": {"code": code, "message": message, "retryable": retryable},
        }
    sys.stdout.write(json.dumps(doc, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def fail_exit(code: str, message: str, retryable: bool = False) -> None:
    """输出失败信息并以稳定退出码结束进程；机器模式附带失败 envelope。"""
    if MACHINE_MODE:
        output_envelope(error=(code, message, retryable))
        raise SystemExit(EXIT_CODES.get(code, 1))
    print(f"error[{code}]: {message}", file=sys.stderr)
    raise SystemExit(EXIT_CODES.get(code, 1))


# ---------------------------------------------------------------------------
# 领域命令结果统计：输出文件快照差分
# ---------------------------------------------------------------------------

def _output_root() -> str:
    """当前存储根：显式 SAVE_DATA_PATH 优先，否则可写根下的 data/。"""
    try:
        import config

        if config.SAVE_DATA_PATH:
            return config.SAVE_DATA_PATH
    except ImportError:
        pass
    return os.path.join(get_writable_root(), "data")


def _count_items(path: str, ext: str) -> int:
    """按存储格式统计文件内条数：jsonl 行数、csv 行数减表头、json 数组元素数。"""
    try:
        with open(path, "rb") as f:
            content = f.read().decode("utf-8", errors="replace")
        if not content.strip():
            return 0
        if ext == "jsonl":
            return sum(1 for line in content.splitlines() if line.strip())
        if ext == "csv":
            return max(sum(1 for line in content.splitlines() if line.strip()) - 1, 0)
        if ext == "json":
            data = json.loads(content)
            if isinstance(data, list):
                return len(data)
            return 1
    except (OSError, json.JSONDecodeError):
        return 0
    return 0


def snapshot_output_files(platform: str, crawler_type: str) -> dict:
    """爬取前对匹配的输出文件做条数快照，供结束后差分。"""
    snapshot: dict = {}
    base = os.path.join(_output_root(), platform)
    if not os.path.isdir(base):
        return snapshot
    for ext in ("jsonl", "csv", "json"):
        ext_dir = os.path.join(base, ext)
        if not os.path.isdir(ext_dir):
            continue
        for name in os.listdir(ext_dir):
            if name.startswith(f"{crawler_type}_") and name.endswith(f".{ext}"):
                path = os.path.join(ext_dir, name)
                snapshot[path] = _count_items(path, ext)
    return snapshot


def diff_output_files(snapshot: dict) -> list:
    """对比快照，返回本轮每个文件的新增条数（新文件计全量）。"""
    additions = []
    for path, old_count in snapshot.items():
        if not os.path.exists(path):
            continue
        ext = path.rsplit(".", 1)[-1]
        new_count = _count_items(path, ext)
        if new_count > old_count:
            additions.append({"path": os.path.abspath(path), "items_added": new_count - old_count})
    return additions


def collect_new_files(platform: str, crawler_type: str, snapshot: dict) -> list:
    """快照差分：既有文件算增量，本轮新建文件算全量。"""
    results = diff_output_files(snapshot)
    base = os.path.join(_output_root(), platform)
    if os.path.isdir(base):
        for ext in ("jsonl", "csv", "json"):
            ext_dir = os.path.join(base, ext)
            if not os.path.isdir(ext_dir):
                continue
            for name in os.listdir(ext_dir):
                if name.startswith(f"{crawler_type}_") and name.endswith(f".{ext}"):
                    path = os.path.join(ext_dir, name)
                    if path not in snapshot and os.path.exists(path):
                        results.append(
                            {"path": os.path.abspath(path), "items_added": _count_items(path, ext)}
                        )
    return results


# ---------------------------------------------------------------------------
# doctor：零网络健康检查
# ---------------------------------------------------------------------------

def login_profile_paths(platform: str) -> list:
    """平台登录态 profile 的两个可能落点（Playwright 与 CDP 自启动模式）。"""
    import config

    browser_data = os.path.join(get_writable_root(), "browser_data")
    suffix = config.USER_DATA_DIR % platform
    return [
        os.path.join(browser_data, suffix),
        os.path.join(browser_data, f"cdp_{suffix}"),
    ]


def has_login_profile(platform: str) -> bool:
    """profile 目录存在且含 Default/ 子目录视为"疑似已登录"。

    语义是 probable 而非 valid：cookie 可能已过期，真伪只能由领域命令
    实际请求判定；doctor 不起浏览器、零网络。
    """
    for path in login_profile_paths(platform):
        if os.path.isdir(os.path.join(path, "Default")):
            return True
    return False


def existing_browser_reachable() -> bool:
    """调试端口上是否已有可连的浏览器（如用户日常 Chrome 开着 9222）。

    经验事实：小红书对新生 profile 的会话不跨浏览器重启生效（扫码/移植
    的会话只在当次会话内有效），而用户日常 Chrome 的成熟会话稳定可用。
    因此登录态来源优先级：已开浏览器 > 自建 profile。
    """
    import socket

    try:
        import config

        port = int(config.CDP_DEBUG_PORT)
    except (ImportError, AttributeError, ValueError):
        port = 9222
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def run_doctor_checks() -> dict:
    """自动可执行的健康检查：无业务副作用、零费用、零网络。"""
    chrome_path = _detect_browser()
    data_dir = os.path.join(get_writable_root(), "data")
    node_source, node_available = _node_status()

    platforms = {}
    for platform in SUPPORTED_PLATFORMS:
        platforms[platform] = {
            "login_profile": has_login_profile(platform),
        }

    return {
        "version": APP_VERSION,
        "machine_mode": MACHINE_MODE,
        "chrome": {"found": chrome_path is not None, "path": chrome_path},
        "node": {"available": node_available, "source": node_source},
        "data_dir": {"path": data_dir, "writable": _is_writable(os.path.dirname(data_dir))},
        "existing_browser": {"reachable": existing_browser_reachable()},
        "platforms": platforms,
    }


def _detect_browser():
    try:
        from tools.browser_launcher import BrowserLauncher

        paths = BrowserLauncher().detect_browser_paths()
        return paths[0] if paths else None
    except Exception:
        return None


def _node_status():
    from tools.app_paths import is_frozen

    if is_frozen():
        from tools.node_runtime import _driver_node_dir

        return ("embedded", _driver_node_dir() is not None)
    return ("system", shutil.which("node") is not None)


def _is_writable(parent_dir: str) -> bool:
    try:
        os.makedirs(parent_dir, exist_ok=True)
        probe = os.path.join(parent_dir, ".mediacrawler_write_probe")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except OSError:
        return False
