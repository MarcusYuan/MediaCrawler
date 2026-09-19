# Nuitka 封装专项研究

> 决策记录：2026-09-19 选定 **Nuitka** 作为封装工具（PyInstaller 降级为兜底备选）。
> 本文是针对 Nuitka 与本项目结合的落地研究，前置文档：《二进制封装需求文档》《二进制封装方案调研》。

## 1. 关键机制确认

### 1.1 Playwright 支持（自动、够用）

- Nuitka 的 Playwright 支持**不需要手动开关**：standalone 模式下标准配置（`standard.nuitka-package.config.yml`）自动生效
- **自动包含 `playwright/driver/node` 二进制**——这正是我们 execjs 需要的 Node，零配置白得
- 浏览器默认不打包；可显式 `--playwright-include-browser=none` 确保绝不误收（CI 机器上如果装过浏览器，不显式排除有被收进包的风险）
- 我们走 CDP 连本机 Chrome，官方教程里最难的"浏览器内嵌"问题与我们无关

### 1.2 ⚠️ 重要修正：onefile 缓存不是默认行为

前期调研说"Nuitka onefile 解压一次后缓存复用"——**这个说法不完整，已修正**：

- 默认解压规格是 `{TEMP}/onefile_{PID}_{TIME}`：**每次运行解压到临时目录、退出删除**（和 PyInstaller 行为相同）
- 要获得缓存复用，必须**显式配置静态路径规格**：

```bash
--onefile-tempdir-spec="{CACHE_DIR}/{PRODUCT}/{VERSION}"
```

- 静态路径下 `--onefile-cache-mode`（默认 `auto`）自动解析为 `cached`：二次启动检测到目录已有负载即跳过解压
- `{CACHE_DIR}` 各平台默认位置：macOS `~/Library/Caches`、Linux `~/.cache`、Windows `%LOCALAPPDATA%`
- **版本联动**：`{VERSION}` 取自 `--product-version`，每次发新版本自动换目录、自动失效重解压——版本号策略（需求 Q5）与缓存机制天然绑定
- 结论：**这条参数是我们构建命令的必选项，漏掉就退化成"每次运行都解压"**，等于白选 Nuitka

### 1.3 数据文件打包与运行时定位（对应前置改动 P1）

- 打包语法：`--include-data-files=libs/*.js=libs/`（`libs/` 下三个 JS 收进包）
- 运行时定位规则（Nuitka 官方明确）：
  - `os.path.dirname(__file__)` → 指向**解压目录**中的模块位置（`--file-reference-choice=runtime` 是 standalone/onefile 默认）→ 适合找打进包里的资源
  - `__compiled__.containing_dir` → Nuitka 专有属性，直接给出分发根目录
  - **官方明确警告：不要依赖 CWD**——正是我们现在的病根（`open('libs/douyin.js')`）
- 源码模式与打包模式可以用 `sys.modules["__main__"].__compiled__` 是否存在来区分

### 1.4 macOS 签名与 Gatekeeper

- macOS 上签名是**强制的、不可关闭**，但默认用 **ad-hoc**（无身份）签名——能本地跑，过不了 Gatekeeper 分发
- 要让用户下载即用（不 `xattr -c`）：需要 Apple Developer ID（$99/年）+ `--macos-sign-identity` + `--macos-sign-notarization`（Nuitka 原生支持公证所需选项）
- CLI 工具**不需要** `--macos-create-app-bundle`（那是 GUI 用的）
- 策略：初期 ad-hoc + 文档说明 `xattr -c`，用户量起来后再投签名

### 1.5 编译器与构建环境（CI 相关）

| 平台 | 编译器 | 备注 |
|------|--------|------|
| macOS | clang（Xcode CLT） | arm64 上 ccache 需 `brew install ccache`（Nuitka 自动识别） |
| Windows | MinGW64（**Nuitka 可自动下载**）或 MSVC 2022+ | MinGW64 产物更快，推荐 |
| Linux | gcc ≥5.1 / clang | 用较老基础镜像构建以获最大 glibc 兼容面 |

ccache 显著加速增量构建（只重编译变化模块），CI 上必须缓存 ccache 目录。

## 2. 我们的构建设计草案

### 2.1 构建命令（草案，待原型验证）

```bash
python -m nuitka \
  --onefile \
  --enable-plugin=playwright \
  --playwright-include-browser=none \
  --include-data-files=libs/*.js=libs/ \
  --onefile-tempdir-spec="{CACHE_DIR}/{PRODUCT}/{VERSION}" \
  --product-name=mediacrawler \
  --product-version=0.1.0 \
  --company-name="MarcusYuan" \
  --output-filename=mediacrawler \
  --output-dir=build \
  --report=build/report.xml \
  main.py
```

说明：

- 入口 `main.py`（async main + `tools.app_runner.run` 包装，Nuitka 直接可用）
- `--report` 生成依赖报告，用于排查漏收的动态导入
- `api/`、`webui/`、`recv_sms.py` 不被 `main.py` 引用链覆盖 → 理论上自动不进包（需验证）
- `main.py` 通过 `CrawlerFactory` 模块级字典引用全部 7 个平台爬虫 → 全平台代码必然进包（符合预期）

### 2.2 双模式资源路径 helper（P1 的实现设计）

```python
# tools/app_paths.py（新增）
import os, sys

def get_app_root() -> str:
    """源码模式返回仓库根；打包模式返回解压/分发目录（libs/ 所在处）。"""
    compiled = getattr(sys.modules.get("__main__"), "__compiled__", None)
    if compiled is not None:
        return compiled.containing_dir
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

改造点（全部为"路径来源替换"，不改行为语义）：

- `douyin/help.py:37` → `execjs.compile(open(os.path.join(get_app_root(), 'libs', 'douyin.js'), ...))`
- `zhihu/help.py:50` → 同上
- 7 个 `core.py` 的 `add_init_script(path="libs/stealth.min.js")` → 绝对路径

### 2.3 execjs 绑定内嵌 Node（P2 的实现设计 + 一个坑）

```python
# tools/node_runtime.py（新增）
def ensure_node_available():
    """源码模式且系统有 node：什么都不做（现状不变）。
    否则把 playwright 自带 node 的目录插到 PATH 最前，让 execjs 探测命中它。"""
    ...driver = os.path.join(os.path.dirname(playwright.__file__), "driver")
    # driver/node 存在则 os.environ["PATH"] = driver + os.pathsep + PATH
```

**坑**：`douyin/help.py` 在**模块导入时**就执行 `execjs.compile()`，而 execjs 的运行时探测发生在 `import execjs` 时。所以 PATH 注入必须发生在 `import execjs` **之前**——落点在 `main.py` 顶部（import 各平台 crawler 之前先调用 `ensure_node_available()`）。原型阶段重点验证这一条。

### 2.4 版本与缓存联动

- 发版流程：改 `--product-version` → 构建产物路径/缓存目录自动隔离 → 用户换新二进制后首次运行重新解压一次
- 建议版本号独立于上游 tag（如 `0.1.0+mc20260918`），同时满足溯源与缓存失效

## 3. CI 构建草案（GitHub Actions）

```yaml
strategy:
  matrix:
    include:
      - { os: macos-15,    artifact: mediacrawler-macos-arm64 }   # Apple Silicon
      - { os: macos-13,    artifact: mediacrawler-macos-x64 }     # Intel
      - { os: ubuntu-22.04, artifact: mediacrawler-linux-x64 }    # 老 glibc 基线
      - { os: windows-2022, artifact: mediacrawler-windows-x64.exe }
```

要点：依赖安装**跳过** `playwright install`（不要浏览器）；macOS 装 ccache；Windows 允许 Nuitka 自动下载 MinGW64；缓存 uv 依赖与 ccache；产物上传 Release。

预期：首次构建每平台 30min~2h（30+ 依赖全量编译），ccache 生效后大幅缩短。

## 4. 风险与待原型验证清单

| # | 风险/疑问 | 验证方式 | 阻断性 |
|---|----------|---------|--------|
| V1 | 30+ 重型依赖能否顺利编译（opencv/pandas/matplotlib/xhshow） | 本机原型构建一次见分晓 | 高（兜底：PyInstaller） |
| V2 | execjs 在 import 前完成 PATH 注入是否生效 | 无系统 Node 容器里跑 dy 冒烟 | 高 |
| V3 | typer/click 动态导入是否完整（Typer 基于 click，社区有零星案例） | `--help` 全参数比对；`--report` 查漏 | 中 |
| V4 | matplotlib 数据文件/词云字体在打包态是否正常 | 词云功能冒烟 | 中 |
| V5 | api/webui 确实没进包 | 体积核对 + report 检查 | 低 |
| V6 | CDP 连本机 Chrome 在打包态正常 | xhs 扫码冒烟 | 高 |
| V7 | Windows Defender 误报 | VirusTotal 扫描 | 中（Windows 分发时） |
| V8 | macOS Gatekeeper（ad-hoc 签名被拦） | 干净 Mac 实测 `xattr -c` | 中（有文档级缓解） |
| V9 | 构建时长/内存是否可接受 | CI 实测 | 低 |

## 5. 建议实施顺序

> 本节为初期规划，实际实施记录见第 7 节"构建记录"。

1. **P1 + P2 适配代码**（`tools/app_paths.py`、`tools/node_runtime.py` + 十来处路径替换）——与封装工具无关，先做且必须做
2. **本机原型构建**（macOS arm64）：解决 V1~V6，量出体积与启动数据
3. **CI 矩阵**：四平台产物 + ccache 缓存
4. **P3/P4**（配置外置、数据目录）：产品形态完善，不阻塞"能不能封装出来"，可在 2、3 之后做

## 7. 构建记录（2026-09-19，macOS arm64 原型）

### 产物与测量

| 指标 | 数值 |
|------|------|
| 单文件体积 | **158MB**（远优于 NFR1 的 400MB 目标） |
| 首次冷启动（含全量解压） | **101 秒** |
| 二次启动（缓存复用） | **2.4~2.5 秒**（缓存生效，约 40 倍提升） |
| 解压缓存目录 | `~/.cache/mediacrawler/0.1.0/`（按 {PRODUCT}/{VERSION} 隔离） |
| 构建耗时 | 首次约 25 分钟；ccache 热后重构建约 13 分钟 |
| 运行基线 | macOS 26.0+（跟随构建机 SDK，未来分发需注意老系统兼容） |

### 验证结论

- ✅ V1 依赖兼容：30+ 依赖（opencv/pandas/matplotlib/xhshow…）Python 层与 C 层全部编译通过
- ✅ V3 CLI 完整性：二进制 `--help` 与源码模式输出逐行一致（仅程序名不同）
- ✅ 内嵌 node：`playwright/driver/node`（116MB）随包分发且保留执行位；剥离系统 PATH（`env PATH=/usr/bin:/bin`，两目录均无 node）后启动成功，证明 execjs 探测命中内嵌 node
- ✅ 资源路径：`libs/*.js`、`docs/` 词云资源、快手 graphql 均在解压目录正确落位并可从任意 CWD 运行
- ⏳ V2 完整链路（dy 真实签名调用）、V6（CDP 连本机 Chrome 爬取）：待用户协助的真人扫码冒烟

### 实施中推翻/修正的三个假设

1. **`__compiled__.containing_dir` 不可用于寻资源根**：它指向可执行文件所在目录（如 `build/`），onefile 下资源实际在解压目录。正确做法：编译模块 `__file__` 上溯（`tools/app_paths.py` 已统一两种模式）
2. **`wordcloud`/`jieba` 的包内数据默认不收录**：`stopwords` 在 import 时读、`dict.txt` 在分词时读，必须 `--include-package-data=wordcloud --include-package-data=jieba`（matplotlib 的 mpl-data 由 Nuitka 包配置自动处理）
3. **`--product-version` 格式受限**：必须 ≤4 段纯数字、每段 ≤65535，PEP 440 的 `0.1.0+mc20260919` 直接 FATAL；构建脚本已拆分"展示版本"与"Nuitka 数字版本"

### 触碰文件清单（与上游同步时重点 review）

`main.py`、`cmd_arg/arg.py`、`config/db_config.py`、`tools/{app_paths,node_runtime,async_file_writer,cdp_browser,slider_util,words}.py`、`store/excel_store_base.py`、`media_downloader/downloader.py`、`media_platform/*/core.py`（7 个）、`media_platform/{douyin,zhihu}/help.py`、`media_platform/kuaishou/graphql.py`；新增 `scripts/build-macos-arm64.sh`

## 8. 参考资料

- [Nuitka Playwright 标准插件（源码）](https://fossies.org)（`nuitka/plugins/standard/PlaywrightPlugin.py`）
- [Nuitka onefile 缓存机制与 --onefile-tempdir-spec（DeepWiki）](https://deepwiki.com/search/how-does-nuitkas-onefile-mode_d54461a8-e436...)（含 `{CACHE_DIR}` 等变量表与 cache-mode 语义）
- [Nuitka 数据文件包含与运行时定位（DeepWiki）](https://deepwiki.com/search/how-should-data-files-nonpytho_26f36135-cc2b-41a1-a1e9-318d314b4ed3)
- [Nuitka macOS 签名/公证/编译器要求（DeepWiki）](https://deepwiki.com/search/what-are-nuitkas-macosspecific_378d3cc3-78ff-4290-9cc2-a9e6490e920a)
- [Nuitka 官方用户手册](https://nuitka.net/doc/user-manual.html)
