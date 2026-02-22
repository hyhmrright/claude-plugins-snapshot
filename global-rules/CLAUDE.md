# 全局开发规则

## 在执行任何 git 操作前，必须先完成自检

**每次准备执行 `git commit`、`git push`、或调用任何 commit/push skill 之前，强制自检：**

```
我在这个 session 里修改了文件吗？
   → 是 → 我是否已经运行了 code-simplifier + code-review？
           → 没有 → 【STOP】立刻运行，不得跳过
           → 是   → 继续执行 git 操作
   → 否 → 当前工作区有未提交的改动吗？（git diff / git diff --cached / git stash list）
           → 有（含 stash 中的改动） → 【STOP】必须先运行 code-simplifier + code-review
           → 无 → 继续执行 git 操作
```

---

## 代码改动强制流程

### 触发条件（满足任意一条即触发）

- 使用 Edit / Write / NotebookEdit 工具修改了任何文件
- 用户意图是将代码变更持久化到 Git 或推送到远程仓库（无论具体用词，包括"同步"、"上传"、"发 PR"、"存档"、"ship"等）
- 准备调用任何 commit / push 相关 skill

### 执行步骤（顺序不可颠倒，不可跳过）

```
写代码 / 修改文件
      ↓
【必须】Skill: code-simplifier:code-simplifier
      ↓
【必须】Skill: code-review:code-review
      ↓
有问题？→ 是 → 修复 → 回到 code-simplifier
    ↓
    否 → 执行 commit / push
```

### 推送 PR 后的补充步骤

在上述流程完成 commit + push 之后，【必须】额外执行：

```
【必须】Skill: code-review:code-review --comment（post review 到 GitHub PR 评论）
```

注意：流程中的 code-review 只输出到终端，不发 GitHub 评论；`--comment` 参数仅在推送 PR 后使用。

---

## 严禁的行为与常见借口

以下任何理由都**不得**作为跳过流程的依据：

| 借口 | 正确做法 |
|------|---------|
| "这只是简单的一行改动" | 无论改动大小，必须执行 |
| "用户只说了 commit，没说要 review" | commit 指令本身就是触发条件 |
| "我刚才已经 review 过类似代码了" | 每次改动后必须重新执行 |
| "这是测试文件，不是核心逻辑" | 测试文件同样适用 |
| "我需要先 push 再 review" | 必须先 review 再 push |
| "用户在催，我先提交" | 流程不因催促而跳过 |
| "这是文档改动，不是代码" | 只要用 Edit/Write 修改了文件就适用 |
| "我已经很熟悉这段代码了" | 熟悉程度不影响流程要求 |
| "这些改动不是我这个 session 里做的" | 只要有未提交改动存在，就必须执行 |
| "用户没有用'commit'这个词" | 只要用户意图是提交/推送，就触发 |
| "这是 --amend，不是新 commit" | --amend 同样修改了历史，必须执行 |
| "改动在 stash 里，工作区是干净的" | stash 中的改动同样需要走完整流程 |

---

## 强制检查点

在调用以下任何工具之前，必须确认 simplifier + review 已执行：

- `Bash` 执行 `git commit`（含 `--amend`）
- `Bash` 执行 `git push`（推送 PR 分支后，还需额外执行 `--comment` 步骤）
- `Skill` 调用任何 `commit-commands:*` skill
- `Skill` 调用任何 `pr-review-toolkit:*` skill（创建 PR 相关）
- `Skill` 调用 `code-review:code-review --comment`（推送 PR 分支后）

**此规则适用于所有项目，无一例外。**
