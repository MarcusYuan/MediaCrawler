# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/main.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#

# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import sys
import io

# Force UTF-8 encoding for stdout/stderr to prevent encoding errors
# when outputting Chinese characters in non-UTF-8 terminals
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# pyexecjs 在 import execjs 时一次性探测 PATH 并缓存结果，此调用必须先于
# 任何会触发 import execjs 的模块（media_platform.douyin 等）执行
from tools.node_runtime import ensure_embedded_node

ensure_embedded_node()

import asyncio
import os
import time
from typing import Optional, Type

import cmd_arg
import config
from database import db
from base.base_crawler import AbstractCrawler
from media_platform.bilibili import BilibiliCrawler
from media_platform.douyin import DouYinCrawler
from media_platform.kuaishou import KuaishouCrawler
from media_platform.tieba import TieBaCrawler
from media_platform.weibo import WeiboCrawler
from media_platform.xhs import XiaoHongShuCrawler
from media_platform.zhihu import ZhihuCrawler
from tools.async_file_writer import AsyncFileWriter
from tools import box_contract
from var import crawler_type_var


class CrawlerFactory:
    CRAWLERS: dict[str, Type[AbstractCrawler]] = {
        "xhs": XiaoHongShuCrawler,
        "dy": DouYinCrawler,
        "ks": KuaishouCrawler,
        "bili": BilibiliCrawler,
        "wb": WeiboCrawler,
        "tieba": TieBaCrawler,
        "zhihu": ZhihuCrawler,
    }

    @staticmethod
    def create_crawler(platform: str) -> AbstractCrawler:
        crawler_class = CrawlerFactory.CRAWLERS.get(platform)
        if not crawler_class:
            supported = ", ".join(sorted(CrawlerFactory.CRAWLERS))
            raise ValueError(f"Invalid media platform: {platform!r}. Supported: {supported}")
        return crawler_class()


crawler: Optional[AbstractCrawler] = None


def _flush_excel_if_needed() -> None:
    if config.SAVE_DATA_OPTION != "excel":
        return

    try:
        from store.excel_store_base import ExcelStoreBase

        ExcelStoreBase.flush_all()
        box_contract.emit_line("[Main] Excel files saved successfully")
    except Exception as e:
        box_contract.emit_line(f"[Main] Error flushing Excel data: {e}")


async def _generate_wordcloud_if_needed() -> None:
    if config.SAVE_DATA_OPTION not in ("json", "jsonl") or not config.ENABLE_GET_WORDCLOUD:
        return

    try:
        file_writer = AsyncFileWriter(
            platform=config.PLATFORM,
            crawler_type=crawler_type_var.get(),
        )
        await file_writer.generate_wordcloud_from_comments()
    except Exception as e:
        box_contract.emit_line(f"[Main] Error generating wordcloud: {e}")


async def main() -> None:
    global crawler

    args = await cmd_arg.parse_cmd()

    # 子命令（doctor/login）不走爬取路径
    if isinstance(args, dict):
        command = args.get("command")
        if command == "doctor":
            return  # doctor 已在子命令内完成检查与输出
        if command == "login":
            await _run_login(args)
            return
        raise box_contract.BoxCliError("invalid_input", f"Unknown command: {command}")

    if args.init_db:
        await db.init_db(args.init_db)
        box_contract.emit_line(f"Database {args.init_db} initialized successfully.")
        return

    # 机器模式：stdout 只输出最终 envelope（见 _run_crawl_json）
    if box_contract.MACHINE_MODE:
        await _run_crawl_json()
        return

    # 数据库保存模式下自动建表，避免首次运行时出现 no such table 错误
    if config.SAVE_DATA_OPTION in ("sqlite", "mysql", "db", "postgres"):
        await db.init_db(config.SAVE_DATA_OPTION)

    crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
    await crawler.start()

    _flush_excel_if_needed()

    # Generate wordcloud after crawling is complete
    # Only for JSON save mode
    await _generate_wordcloud_if_needed()


async def _run_login(args: dict) -> None:
    """login 子命令：有头 + CDP 自启动，登录态落 browser_data，只登录不爬取。"""
    global crawler

    if args["lt"] == "phone":
        box_contract.fail_exit(
            "invalid_input",
            "phone login requires an external SMS receiver; use qrcode or cookie",
        )

    # 哨兵值：7 个平台的 start() 对未知 CRAWLER_TYPE 均不分发爬取，只完成会话准备与登录
    config.CRAWLER_TYPE = "login"
    config.ENABLE_CDP_MODE = True
    config.CDP_CONNECT_EXISTING = False  # 登录态必须落本地 browser_data，不写用户日常 Chrome
    config.SAVE_LOGIN_STATE = True
    config.HEADLESS = False
    config.CDP_HEADLESS = False

    try:
        crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
        await crawler.start()
    except SystemExit as exc:
        # 各平台登录失败路径直接 sys.exit()（不带参数时退出码为 0，会被误读为成功），
        # 这里统一转成明确的 auth_required 失败
        box_contract.fail_exit(
            "auth_required",
            "login did not complete; scan the QR code in time and retry",
            retryable=True,
        )
        raise exc  # pragma: no cover - fail_exit 必然抛出，此行仅为类型完整

    # 登录完成以"平台 API 接受会话"为准：扫码成功只代表拿到 cookie，
    # 全新设备指纹可能还差滑块/验证激活。轮询期间浏览器窗口保持打开，
    # 如窗口中出现滑块验证，请当场完成。
    # 注意不能按 "attr.endswith('_client')" 直接取第一个：create_xxx_client
    # 这类构造方法也会命中且按字母序更靠前，必须校验 pong 可调用。
    client = None
    for attr in dir(crawler):
        value = getattr(crawler, attr, None)
        if attr.endswith("_client") and hasattr(value, "pong"):
            client = value
            break
    api_verified = False
    if client is not None:
        box_contract.emit_line("Waiting for the platform API to accept the session (up to 90s)...")
        for _ in range(30):
            api_verified = await client.pong()
            if api_verified:
                break
            await asyncio.sleep(3)

    if not api_verified:
        box_contract.fail_exit(
            "auth_required",
            "login cookies saved but the platform API has not accepted this session; "
            "re-run login and complete any verification shown in the browser window",
            retryable=True,
        )

    # 正常收尾由 app_runner 的 async_cleanup 完成（优雅关浏览器，确保 cookie 落盘）
    if box_contract.MACHINE_MODE:
        profiles = [
            os.path.abspath(p)
            for p in box_contract.login_profile_paths(config.PLATFORM)
            if os.path.isdir(os.path.join(p, "Default"))
        ]
        box_contract.output_envelope(
            result={
                "platform": config.PLATFORM,
                "login_profiles": profiles,
                "api_verified": api_verified,
            }
        )


async def _run_crawl_json() -> None:
    """机器模式爬取：stdout 仅一个最终 JSON envelope，日志全部在 stderr。"""
    global crawler
    started = time.monotonic()

    # 机器模式只消费已有登录态：忽略 --lt，绝不进入交互登录。
    # 登录态来源优先级：已开的调试口浏览器（成熟会话，稳定）> 自建 profile
    # （注：小红书对新生 profile 的会话不跨浏览器重启生效，自建 profile 仅在
    # 登录当次会话可靠，故不强制 CDP_CONNECT_EXISTING=False，保持上游默认）
    config.LOGIN_TYPE = "cookie"
    if not (
        box_contract.existing_browser_reachable()
        or box_contract.has_login_profile(config.PLATFORM)
    ):
        box_contract.fail_exit(
            "auth_required",
            f"no usable login state for platform '{config.PLATFORM}'; start Chrome with "
            f"--remote-debugging-port=9222 (logged in), or run "
            f"'mediacrawler login --platform {config.PLATFORM}'",
        )

    if config.SAVE_DATA_OPTION in ("sqlite", "mysql", "db", "postgres"):
        await db.init_db(config.SAVE_DATA_OPTION)

    snapshot = box_contract.snapshot_output_files(config.PLATFORM, config.CRAWLER_TYPE)
    try:
        crawler = CrawlerFactory.create_crawler(platform=config.PLATFORM)
        await crawler.start()
        _flush_excel_if_needed()
        await _generate_wordcloud_if_needed()
    except SystemExit:
        # 平台代码在登录态失效等场景直接 sys.exit()；机器模式下转成可解析的失败
        box_contract.fail_exit(
            "auth_required",
            "saved login state was rejected; re-run 'mediacrawler login'",
            retryable=True,
        )
    except box_contract.BoxCliError as exc:
        box_contract.fail_exit(exc.code, exc.message, exc.retryable)
    except Exception as exc:  # 机器模式下不裸抛 traceback，统一转失败 envelope
        if type(exc).__name__ == "RetryError":
            # pong 失败→空 cookie 空转登录→请求被拒的典型链条：会话未被平台接受
            box_contract.fail_exit(
                "auth_required",
                "requests rejected after retries; saved session may have expired, "
                "re-run 'mediacrawler login'",
                retryable=True,
            )
        box_contract.fail_exit("internal_error", f"{type(exc).__name__}: {exc}")

    outputs = box_contract.collect_new_files(config.PLATFORM, config.CRAWLER_TYPE, snapshot)
    box_contract.output_envelope(
        result={
            "platform": config.PLATFORM,
            "crawler_type": config.CRAWLER_TYPE,
            "keywords": config.KEYWORDS,
            "outputs": outputs,
            "total_items_added": sum(o["items_added"] for o in outputs),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
    )


async def async_cleanup() -> None:
    global crawler
    if crawler:
        if getattr(crawler, "cdp_manager", None):
            try:
                await crawler.cdp_manager.cleanup(force=True)
            except Exception as e:
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnected" not in error_msg:
                    box_contract.emit_line(f"[Main] Error cleaning up CDP browser: {e}")

        elif getattr(crawler, "browser_context", None):
            try:
                await crawler.browser_context.close()
            except Exception as e:
                error_msg = str(e).lower()
                if "closed" not in error_msg and "disconnected" not in error_msg:
                    box_contract.emit_line(f"[Main] Error closing browser context: {e}")

    if config.SAVE_DATA_OPTION in ("db", "sqlite"):
        await db.close()

if __name__ == "__main__":
    from tools.app_runner import run

    def _force_stop() -> None:
        c = crawler
        if not c:
            return
        cdp_manager = getattr(c, "cdp_manager", None)
        launcher = getattr(cdp_manager, "launcher", None)
        if not launcher:
            return
        try:
            launcher.cleanup()
        except Exception:
            pass

    run(main, async_cleanup, cleanup_timeout_seconds=15.0, on_first_interrupt=_force_stop)
