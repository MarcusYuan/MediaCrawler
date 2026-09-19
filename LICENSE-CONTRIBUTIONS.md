# 增量贡献授权（License for Fork Contributions）

本文件是本 fork **新增文件**的授权声明。它与上游 `LICENSE`（非商业学习使用许可证 1.1）
构成两层授权结构，整体说明见 `NOTICE`。

## 适用范围（仅限以下本 fork 新增的文件）

- `tools/app_paths.py` —— 双模式路径解析适配层
- `tools/node_runtime.py` —— 内嵌 Node 注入
- `tools/box_contract.py` —— 机器输出合同层（envelope / 错误码 / doctor / 统计）
- `scripts/build.py`、`scripts/build-macos-arm64.sh` —— 构建脚本
- `tests/test_box_contract.py` —— 合同测试
- `docs/Fork仓库同步规范.md`
- `docs/二进制封装需求文档.md`
- `docs/二进制封装方案调研.md`
- `docs/Nuitka封装专项研究.md`
- `docs/PluginBox接入需求文档.md`
- `README.md` —— 本 fork 重写后的内容
- `NOTICE`、`LICENSE-CONTRIBUTIONS.md`
- `.github/workflows/release.yml`

## 不适用范围

- 上游 MediaCrawler 的全部原始代码；
- 本 fork 对上游文件（如 `main.py`、`cmd_arg/arg.py`、`tools/` 与 `media_platform/` 下的既有文件等）
  所做的任何修改——这些修改内嵌于上游文件，随所在文件一并受上游 `LICENSE` 约束；
- 整份组合作品及其二进制产物的分发与使用（始终受上游 `LICENSE` 约束，见 `NOTICE`）。

## 授权条款（MIT License）

Copyright (c) 2026 MarcusYuan (byebye758)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
