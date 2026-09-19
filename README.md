# MediaCrawler 单文件版

一个文件就能用的社交媒体内容采集工具。从 [Releases](https://github.com/MarcusYuan/MediaCrawler/releases)
下载可执行文件即可开始——不需要安装 Python，不需要装依赖，唯一的要求是电脑上有 Chrome。

支持在小红书、抖音、快手、B 站、微博、贴吧、知乎上采集笔记/视频内容、评论和媒体文件。

> 本项目基于开源项目 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 打包而成，
> 仅供学习与研究用途，请遵守各平台的使用条款并合理控制采集频率。

## 安装（一分钟）

1. 从 [Releases](https://github.com/MarcusYuan/MediaCrawler/releases) 下载对应系统的文件
   （macOS 选 `macos-arm64`（M 系列芯片）或 `macos-x64`（Intel），Windows 选 `.exe`，Linux 选 `linux-x64`）
2. macOS / Linux：赋予执行权限并去掉下载限制：

```bash
mv mediacrawler-* mediacrawler
chmod +x mediacrawler
xattr -c mediacrawler        # 仅 macOS 需要：解除"无法验证开发者"拦截
```

3. 检查环境就绪：

```bash
./mediacrawler doctor
```

## 上手：三个最常见的任务

**任务一：搜关键词，采集笔记和评论**

```bash
./mediacrawler --platform xhs --keywords "露营装备" --get_comment true
```

首次运行会打开 Chrome 显示小红书登录页，用手机 App 扫码即可；登录一次后会记住，
之后不再需要（登录状态查询：`./mediacrawler doctor`）。

**任务二：采集指定的帖子/视频**

```bash
./mediacrawler --platform xhs --type detail \
  --specified_id "笔记ID或完整链接，多个用逗号分隔" --get_comment true
```

**任务三：采集某个创作者的全部内容**

```bash
./mediacrawler --platform dy --type creator --creator_id "创作者ID或主页链接"
```

**数据在哪？** 全部落在 `~/.mediacrawler/data/<平台>/` 下，默认 jsonl 格式
（每行一条 JSON，可直接用 Python/pandas 处理），可用 `--save_data_option` 换成
csv / excel / json / sqlite 等。需要下载图片视频加 `--get_media true`。

## 常用参数速查

| 参数 | 说明 | 示例 |
|---|---|---|
| `--platform` | 平台：xhs / dy / ks / bili / wb / tieba / zhihu | `--platform xhs` |
| `--type` | search（搜关键词）/ detail（指定帖子）/ creator（创作者） | `--type search` |
| `--keywords` | 搜索关键词，多个逗号分隔 | `--keywords "咖啡,手冲"` |
| `--specified_id` | detail 模式的帖子 ID/链接列表 | `--specified_id "a,b"` |
| `--creator_id` | creator 模式的创作者 ID/链接列表 | `--creator_id "xxx"` |
| `--get_comment` | 是否抓评论 | `--get_comment true` |
| `--get_media` | 是否下载图片/视频 | `--get_media true` |
| `--crawler_max_notes_count` | 最多采集条数 | `--crawler_max_notes_count 100` |
| `--save_data_option` | 存储格式：jsonl / csv / excel / json / sqlite | `--save_data_option csv` |
| `--headless` | 是否隐藏浏览器窗口 | `--headless true` |

完整参数说明：`./mediacrawler --help`

## 登录与浏览器

- 工具会启动你电脑上的 Chrome 完成登录和采集，**不修改你日常使用的浏览器配置**
- 每个平台首次使用时登录一次（扫码或 `--lt cookie` 传入 Cookie），之后自动复用
- 登录失效时重新运行一次即可：`./mediacrawler login --platform xhs`
- 想直接使用你已登录的 Chrome？用调试模式启动它，工具会自动连接：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222
```

## 进阶：给程序调用（--json 模式）

在命令后加 `--json`，输出变为机器可读格式：**stdout 只有一个 JSON 结果**
（含数据文件路径、条数统计），日志全部走 stderr，退出码表示结果类型
（`0` 成功、`4` 未登录、`2` 参数错误等），适合脚本和自动化工具调用：

```bash
./mediacrawler --platform xhs --keywords "咖啡" --json
```

```json
{"contract_version": "1", "ok": true, "result": {"platform": "xhs", "keywords": "咖啡",
 "outputs": [{"path": "~/.mediacrawler/data/xhs/jsonl/search_contents_xxx.jsonl",
 "items_added": 20}], "total_items_added": 20, "elapsed_seconds": 53.9}}
```

## 常见问题

| 现象 | 处理 |
|---|---|
| macOS 提示"无法验证开发者" | `xattr -c mediacrawler` 后再运行 |
| 提示 `auth_required` / 需要登录 | 运行 `./mediacrawler login --platform <平台>` 扫码登录 |
| 没有弹出浏览器 / 找不到 Chrome | 安装 Chrome 或 Edge 后重试；`doctor` 可查看检测结果 |
| 采集被平台限制 | 降低频率与数量（调小 `--crawler_max_notes_count`），稍后再试 |
| 想看工具自身状态 | `./mediacrawler doctor`（检查 Chrome、登录态、数据目录、内置组件） |

## 从源码构建

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt nuitka
.venv/bin/python scripts/build.py          # 加 --dry-run 可先预览构建命令
```

## 授权

本项目为两层授权：上游代码遵循其[非商业学习使用许可](LICENSE)；本项目新增部分以
[MIT](LICENSE-CONTRIBUTIONS.md) 授权（构成说明见 [NOTICE](NOTICE)）。
**整体（含发布的二进制）的使用与分发受上游许可约束：仅供学习研究，禁止商用。**

## 更多文档

- [常见问题（上游版）](docs/常见问题.md) · [项目代码结构](docs/项目代码结构.md)
- [Fork 同步规范](docs/Fork仓库同步规范.md) · [发布与维护指南](docs/发布与维护.md)（CI/CD、发版流程）
- [二进制封装系列文档](docs/二进制封装需求文档.md)（需求/调研/实测记录）
