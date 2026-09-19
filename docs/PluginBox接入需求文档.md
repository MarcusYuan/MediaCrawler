# MediaCrawler 接入 Plugin Box 需求文档

> 版本：v0.1（需求阶段）
> 前置文档：《二进制封装需求文档》《二进制封装方案调研》《Nuitka封装专项研究》
> 事实源：plugin-box `docs/skill-cli-contracts.md` v0.24（§6 最低合同、§6.1 接入顺序、§6.2 公共入口、§7.1 机器输出合同 v1）、`docs/contracts/cli-package-box-v3.schema.json`、参照实现 `managed-clis/packages/box-asr`

## 1. 背景与目标

第一阶段已产出 158MB 自包含单文件二进制（macOS arm64），满足了 Plugin Box Managed CLI 最低合同中最硬的一条——"不依赖调用方 CWD 与系统语言 Runtime"。本文档定义第二阶段：**为该二进制补齐 Plugin Box 平台合同面，并完成 CLI Package 注册**。

结论已确认：**可行**。所有差距均为增量式 CLI 改造，不触碰爬虫内核。

## 2. 差距基线（对照 §6 最低合同）

| 合同要求 | 现状 | 本阶段动作 |
|---|---|---|
| 不依赖 CWD / 系统 Runtime | ✅ 二进制已满足 | 无 |
| `--help` | ✅ | 无 |
| 稳定 `--version` | ⚠️ 格式不符 | FR1（裸 semver，见下） |
| stdout=结果 / stderr=日志分离 | ❌ 日志混在 stdout | FR3 |
| 机器可读输出 | ❌ 仅 jsonl 文件 | FR3 |
| 可自动运行健康检查 | ❌ | FR2（`doctor --json`） |
| 非交互默认 | ⚠️ 扫码/手机登录交互 | FR4（登录生命周期拆分） |
| 稳定退出码 | ⚠️ 仅 0/1 | FR5 |
| 黑盒验收样例 | ❌ | FR6 |
| 取消/失败清理 | ✅ app_runner + CDP 清理策略 | 无（回归覆盖） |
| 不输出 Secret | ⚠️ 待核验 Cookie 打印路径 | FR8 |

## 3. 功能需求

### FR1 `--version` 改为裸 semver

参照 `box-asr/tests/version_contract.rs` 的黑盒断言：stdout **只含精确版本号**（如 `0.1.0`），stderr 为空，退出码 0。

- 现输出 `mediacrawler 0.1.0+mc20260919` → 改为 `0.1.0`（产品名与构建信息移入 `--license`/about 或 stderr 不输出）
- 版本号单一事实源：`cmd_arg/arg.py` 的 `APP_VERSION` 与构建脚本 `MC_VERSION_NUM` 必须同源（建议抽为共享常量）

### FR2 `doctor --json`

自动运行、**无业务副作用、零费用、无网络请求**，区分"环境故障"与"未配置"：

```json
{
  "contract_version": "1", "ok": true,
  "result": {
    "chrome": {"found": true, "path": "/Applications/..."},
    "browser_data": {"platforms_with_login": ["xhs"]},
    "data_dir": {"path": "~/.mediacrawler", "writable": true},
    "embedded_node": {"available": true}
  }
}
```

- 检查项：Chrome 探测（复用 `tools/browser_launcher.py`）、各平台登录态（browser_data 存在性与新鲜度）、`~/.mediacrawler` 可写、内嵌 node 可执行
- 无登录属于**健康**但 `platforms_with_login` 为空；登录态缺失由领域命令在运行时报 `auth_required`，doctor 不因此判失败

### FR3 领域命令 `--json`（stdout/stderr 分离）

- 全局 `--json` 标志：开启后** stdout 仅输出一个最终 JSON 文档**（§7.1 envelope：`{contract_version, ok, result|error}`），全部日志/进度重定向 stderr（UTF-8）
- `result` 至少包含：输出文件绝对路径清单、各类条数统计（notes/comments）、平台与关键词、耗时
- 不带 `--json` 时保持现有人类可读行为（日志格式不变）

### FR4 登录生命周期拆分（非交互默认的关键）

- 新增 `login` 子命令：**显式交互**（TTY 下扫码/手机/Cookie），按平台执行一次，登录态写入 `~/.mediacrawler/browser_data/`
- 领域命令（search/detail/creator）**永不交互**：发现登录态缺失/失效时返回 `error.code=auth_required`、退出码非 0，提示先运行 `login`
- 现有 `--lt qrcode/phone/cookie` 运行参数保留（源码模式行为不变），但 `--json` 模式下若触发交互登录直接报错拒绝

### FR5 稳定错误码

采用 §7.1 基础错误码子集：`invalid_input`、`not_configured`（如 Chrome 未找到）、`auth_required`、`timeout`、`cancelled`、`rate_limited`（目标平台风控）、`internal_error`。`ok` 与退出码严格一致；文档化每个领域命令的错误类别。

### FR6 黑盒验收样例

按 Catalog 准入要求提供可确定性解析的成功/失败样例各至少一组（如：`doctor --json` 成功样例、无登录态时 search 的 `auth_required` 失败样例），交由黑盒合同测试消费。

### FR8 Secret 核验

梳理并确保任何日志/JSON 输出路径不打印 Cookie 原文、不落盘明文凭证。

### FR7（候选，暂缓）`test --json`

爬虫的"真实领域测试"必然访问目标平台、消耗账号信誉——与"test 可自动执行"存在张力。**本阶段不实现**，健康验证以 doctor 为准。是否提供降级版 test（如仅本地解析固定样例）列入开放问题。

## 4. 结构性要求

1. **纯增量**：现有全部参数与 `python main.py` 用法不变；新增能力以 typer 子命令（`doctor`、`login`）与全局 `--json` 实现；源码模式零行为变化
2. **与上游同步优先**：改动集中在 `cmd_arg/`、`main.py` 与新增模块（如 `tools/box_contract.py`），触碰文件数最小化
3. **`--json` 实现层**：日志 handler 按模式分流（stdout→stderr）+ 结果 envelope 汇总，不动 store 层（jsonl 照常落盘，envelope 引用其路径）

## 5. CLI Package 清单需求（`cli-package.box.json` v3 草案）

| 字段 | 值 / 决策 |
|---|---|
| `id` | `mediacrawler`（命名风格见开放问题 Q2） |
| `target` | `darwin / arm64`；`minimum_os_version` **待定**（当前二进制基线 macOS 26+，见 Q3） |
| `executable` | `mediacrawler`（单文件，files[] 仅一项——onefile 形态使逐文件 SHA-256 校验极简） |
| `managed_cli_contract_version` | `1` |
| `machine_output` | `json / utf-8` |
| `health_check` | `doctor --json` |
| `permissions.network` | 目标平台（xhs/dy/ks/bili/wb/tieba/zhihu） |
| `permissions.credentials` | 用户平台登录态（Cookie/browser_data） |
| `permissions.file_write` | `~/.mediacrawler/`（数据、登录态、解压缓存） |
| `permissions.side_effects` | 访问目标平台并可能触发风控/账号限制；**如实声明** |
| `data_policy.preserve_on_update` | `data/`、`browser_data/`（用户数据与登录态跨版本保留） |
| `data_policy.remove_on_uninstall` | 解压缓存目录（`~/.cache/mediacrawler/`） |
| `presentation` | zh-CN + en 双语（照 box-asr 结构） |

## 6. 约束

1. 上游 LICENSE（非商业学习许可）：分发与用途限制延续第一阶段结论
2. 爬虫性质：permissions/side_effects 如实声明是准入诚信问题，不做弱化
3. 构建基线：`target.minimum_os_version` 与实际二进制的部署目标必须一致，不得虚标

## 7. 开放问题

| # | 问题 | 备注 |
|---|---|---|
| Q1 | 版本单一事实源落点（`APP_VERSION` 常量 vs 构建注入） | 建议常量 + 构建脚本读取同一文件 |
| Q2 | 包 id 命名：`mediacrawler` 还是 `box-media-crawler`（对齐 box-* 惯例） | 若走官方 CLI 体系建议后者 |
| Q3 | `minimum_os_version` 策略：仅 mac26+ / 降部署目标重出包 | 影响受众面，需实测老系统 |
| Q4 | 是否同时注册 Skill Package（Agent 触发的采集技能，声明 CLI 依赖与确认边界） | 建议第二阶段后单独评估 |
| Q5 | 领域命令面是否需要子命令化（`crawl search ...`） | 当前 options 风格不违反合同，改动纯属体验 |
| Q6 | `test --json` 降级版是否提供 | 见 FR7 |

## 8. 验收标准

1. [ ] `--version` stdout 为裸 semver、stderr 空、退出码 0（box-asr 式断言）
2. [ ] `doctor --json` 无网络无费用可自动运行，正确区分环境故障与未登录
3. [ ] 任一领域命令 `--json`：stdout 单 JSON 文档、日志全在 stderr、`ok` 与退出码一致、`result` 含输出路径与统计
4. [ ] 无登录态时领域命令返回 `auth_required` 且非交互
5. [ ] `login` 子命令可完成 xhs 扫码并持久化登录态；此后领域命令非交互可用
6. [ ] 黑盒成功/失败样例可被确定性解析
7. [ ] 源码模式（`python main.py`，不带新参数）行为与第一阶段完全一致
8. [ ] 清单 v3 通过 schema 校验，permissions/data_policy 如实
