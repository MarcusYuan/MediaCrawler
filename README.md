# MediaCrawler 单文件发行版

[![Release](https://img.shields.io/github/v/release/MarcusYuan/MediaCrawler?display_name=tag)](https://github.com/MarcusYuan/MediaCrawler/releases)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-blue)](https://github.com/MarcusYuan/MediaCrawler/releases)
[![Upstream](https://img.shields.io/badge/upstream-NanmiCoder%2FMediaCrawler-orange)](https://github.com/NanmiCoder/MediaCrawler)

把多平台社交媒体爬虫 **MediaCrawler** 打包成**一个可执行文件**的发行版：无需安装
Python、无需 pip 依赖、无需 Node.js、无需下载浏览器——**只要你的电脑装了 Chrome**，
下载即用。

> 本仓库是 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的 fork。
> 爬虫能力全部来自上游并持续同步；本仓库的增量是**单文件打包**与**机器可读 CLI
> 合同面**。授权结构见 [NOTICE](NOTICE)。

## 它是什么

```
下载一个 ~160MB 的可执行文件
  → 运行 mediacrawler --platform xhs --type search --keywords "美食"
  → 本机 Chrome 自动启动、复用登录态、完成爬取
  → 数据落到 ~/.mediacrawler/data/
```

- **7 个平台**：小红书（xhs）、抖音（dy）、快手（ks）、B 站（bili）、微博（wb）、贴吧（tieba）、知乎（zhihu）
- **单文件自包含**：Python 运行时、全部依赖、Node.js（签名用）全部内嵌；首次运行解压一次并缓存，之后秒级启动
- **用你的 Chrome**：CDP 模式驱动本机 Chrome（程序用你的 Chrome，不内置、不下载浏览器）
- **两种使用形态**：人类可读模式 + `--json` 机器模式（stdout 单 JSON envelope、stderr 日志、稳定退出码，面向自动化/Agent 调用）

## 快速开始

1. 从 [Releases](https://github.com/MarcusYuan/MediaCrawler/releases) 下载对应平台的文件
2. macOS/Linux：`chmod +x mediacrawler-* && mv mediacrawler-* mediacrawler`
   （macOS 未签名二进制首次运行前需执行 `xattr -c mediacrawler`）
3. 前置检查 + 爬取：

```bash
./mediacrawler doctor                       # 健康检查：Chrome/登录态/数据目录/内嵌 Node
./mediacrawler --platform xhs --type search --keywords "美食" --get_comment true
```

首次使用某个平台需要登录一次（见下节），之后自动复用。

## 两种使用形态

### 人类模式（默认）

```bash
./mediacrawler --platform xhs --lt qrcode --type search --keywords "咖啡"
```

日志与进度直接可读；全部参数见 `--help`；版本见 `--version`；许可证见 `--license`。

### 机器模式（`--json`）

面向脚本/Agent/工作流调用：

```bash
./mediacrawler --platform xhs --type search --keywords "咖啡" --json
```

- **stdout 只有一个最终 JSON 文档**（成功/失败 envelope），日志与进度全部走 stderr
- `result` 包含输出文件绝对路径、条数统计、耗时；失败时 `error` 带稳定错误码
- 稳定退出码：`0` 成功；`1` internal_error；`2` invalid_input；`3` not_configured；
  `4` auth_required；`5` rate_limited；`6` timeout；`130` cancelled
- 机器模式**绝不交互**：缺登录态直接返回 `auth_required`，不弹二维码

```json
{"contract_version": "1", "ok": true, "result": {"platform": "xhs", "crawler_type": "search",
 "keywords": "咖啡", "outputs": [{"path": "~/.mediacrawler/data/xhs/jsonl/search_contents_2026-09-19.jsonl",
 "items_added": 20}], "total_items_added": 20, "elapsed_seconds": 53.9}}
```

健康检查与登录：

```bash
./mediacrawler doctor --json                # 零网络零费用：Chrome/登录态/数据目录/Node
./mediacrawler login --platform xhs         # 交互登录一次（扫码或 Cookie）
```

数据默认存 `~/.mediacrawler/data/`（jsonl/csv/json/excel/sqlite 等，由
`--save_data_option` 决定）；媒体下载用 `--get_media true`。

## 登录与浏览器架构（重要）

工具与你的 Chrome 的关系分三层：

1. **Chrome 程序本身**：直接用你本机安装的 Chrome（CDP 模式自动探测）
2. **登录态**：默认使用**独立的工作 profile**（`~/.mediacrawler/browser_data/`），
   与你日常浏览器隔离；也可以连接你已开启调试端口（`--remote-debugging-port=9222`）
   的 Chrome 直接复用其登录态
3. **实测结论（登录态来源优先级）**：小红书等平台对新生 profile 的会话**不跨浏览器
   重启生效**，而长期使用的 Chrome 成熟会话稳定可靠——因此工具优先连接已开调试口的
   浏览器，自建 profile 作为无浏览器环境的回退（`login` 子命令，扫码/Cookie 一次）

## 从源码构建

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt nuitka
brew install ccache                                  # macOS，可选但强烈建议
.venv/bin/python scripts/build.py                    # 跨平台构建脚本（--dry-run 可预览命令）
# 等价本地入口：./scripts/build-macos-arm64.sh
```

版本号单一事实源：`tools/box_contract.py` 的 `APP_VERSION`。

## 与上游的关系

- 上游：[NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（爬虫全部能力来源，持续同步更新）
- 同步策略：[docs/Fork仓库同步规范.md](docs/Fork仓库同步规范.md)（upstream fetch + merge，改动保持增量式以控制冲突面）
- 本仓库增量：双模式路径适配层（`tools/app_paths.py`）、内嵌 Node 注入（`tools/node_runtime.py`）、
  机器输出合同层（`tools/box_contract.py`）、跨平台构建（`scripts/build.py`）、
  四平台发布流水线（`.github/workflows/release.yml`）

## 授权

本仓库为两层授权结构（详见 [NOTICE](NOTICE)）：

- 上游代码及其修改：[LICENSE](LICENSE)（非商业学习使用许可证 1.1，原文未动）
- 本 fork 新增文件：[LICENSE-CONTRIBUTIONS.md](LICENSE-CONTRIBUTIONS.md)（MIT）

**整份组合作品（含二进制产物）的使用与分发始终受上游非商业学习许可约束。**

## 文档索引

| 文档 | 内容 |
|---|---|
| [Fork仓库同步规范](docs/Fork仓库同步规范.md) | 与上游的同步流程 |
| [二进制封装需求文档](docs/二进制封装需求文档.md) | 打包目标、依赖审计、验收标准 |
| [二进制封装方案调研](docs/二进制封装方案调研.md) | PyInstaller/Nuitka 选型对比 |
| [Nuitka封装专项研究](docs/Nuitka封装专项研究.md) | 构建参数、实测数据、踩坑记录 |
| [PluginBox接入需求文档](docs/PluginBox接入需求文档.md) | 机器输出合同面与接入验收 |

## 使用须知（承自上游原则）

本项目仅供学习和研究目的使用：不得用于商业用途；使用时应遵守目标平台的使用条款
和 robots.txt 规则；不得进行大规模爬取或对平台造成运营干扰；应合理控制请求频率，
避免给平台带来不必要的负担。
