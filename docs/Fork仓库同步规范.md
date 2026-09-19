# Fork 仓库同步规范

> 本文档说明本仓库（fork 自 `NanmiCoder/MediaCrawler`）与上游原仓库的关系，以及日常开发、同步上游的操作规范。

## 1. 三个仓库的关系

| 名称 | 地址 | 角色 | 权限 |
|------|------|------|------|
| `upstream` | `https://github.com/NanmiCoder/MediaCrawler` | 原作者的仓库，唯一的"更新源头" | 只读，只 fetch，永不 push |
| 本地仓库 | `~/workspace/MediaCrawler` | 实际开发的地方，所有修改发生在这里 | 读写 |
| `origin` | `https://github.com/MarcusYuan/MediaCrawler` | 我们自己的 fork，云端版本 + 备份 | 读写 |

数据流向：

```
upstream（上游）
    │  git fetch upstream          ← 只下载上游新提交，不改动任何代码
    ▼
本地仓库
    │  git merge upstream/main     ← 把上游提交合并进我们的 main
    │  git push origin main        ← 把我们的版本推到自己的 fork
    ▼
origin（我们的 fork）
```

## 2. Fork 的本质（理解这一节，后面的都是细节）

- Fork 是**某一时刻的完整快照复制**。点击 Fork 那一刻起，两个仓库就是完全独立的仓库。
- GitHub 上的 "forked from" 标记只是元数据，**不产生任何自动同步**：
  - 上游更新 → 我们的 fork 不会自动更新
  - 我们改代码 → 上游不会知道（除非主动提 PR）
- 因此"同步上游"永远是一次**手动发起的单向操作**：`fetch`（下载）+ `merge`（合并进我们的历史）。
- 同步不会覆盖我们的修改。我们的提交永远保留在自己的历史里；只有当双方改了同一文件的同一处时才产生冲突，需人工裁决。

## 3. 日常开发规范

1. 直接在 `main` 分支（或功能分支）上开发，与平常无异。
2. 提交信息使用有意义的中文描述，与现有风格一致（如 `feat(ks): xxx`、`fix(dy): xxx`）。
3. 改动完成后：

   ```bash
   git push origin main
   ```

## 4. 同步上游规范

当上游（原作者）有新提交（修 bug、新功能等）需要引入时：

```bash
# 1. 确保工作区干净（未提交的改动先 commit 或 stash）
git status

# 2. 拉取上游最新提交（只下载，不影响代码）
git fetch upstream

# 3. 合并进本地 main
git merge upstream/main

# 4. 推回自己的 fork，保持云端同步
git push origin main
```

原则：

- **用 merge，不用 rebase**。rebase 会改写历史、需要 force push，fork 场景下风险大于收益。
- 同步前**先看差异**：`git log main..upstream/main --oneline` 可以先看看上游到底更新了什么，再决定是否合并。
- 同步频率随意，建议在需要上游某个修复/功能时及时同步，避免落后太多导致大冲突。

## 5. 冲突处理

merge 时如果报 `CONFLICT`，说明我们和上游改了同一处代码：

```bash
git status                  # 查看哪些文件冲突
# 打开冲突文件，处理 <<<<<<< ======= >>>>>>> 标记，决定保留哪边（或融合两边）
git add <冲突文件>
git commit                  # 完成合并提交
git push origin main
```

如果合并进行到一半想放弃：

```bash
git merge --abort
```

## 6. 禁止事项

- ❌ 不要向 `upstream` push（没有权限，也不应该有此意图）
- ❌ 不要对已推送的 `main` 历史做 rebase / force push
- ❌ 不要在 GitHub 网页上用 "Sync fork" 按钮丢弃自己的修改（Discard commits 会**删掉自己的所有改动**）
