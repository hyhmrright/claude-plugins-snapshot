# 全局开发规则

## 代码改动流程（必须遵守）

### 触发条件

以下任意一种情况都必须触发此流程，没有例外：
- 修改了任何代码文件
- 用户说"commit"、"push"、"提交"、"推送"、"创建 PR"等操作指令
- 调用任何 commit/push 相关 skill 之前

### 日常开发循环

每次完成代码改动后，必须按以下流程执行，循环直到无问题为止：

1. **code-simplifier**：通过 `Skill` 工具调用 `code-simplifier:code-simplifier`，对刚改动的代码进行简化和优化
2. **code-review**：通过 `Skill` 工具调用 `code-review:code-review`（等同于 `/code-review`），对优化后的代码进行审查（只输出到终端，不发 GitHub 评论）
3. **如果 review 发现问题**：修复问题，回到第 1 步
4. **如果 review 无问题**：流程结束，可以提交

```
改动代码（或收到 commit/push 指令）
      ↓
Skill: code-simplifier:code-simplifier
      ↓
Skill: code-review:code-review
      ↓
有问题？ → 是 → 修复 → 回到 code-simplifier
    ↓
    否 → 完成，执行 commit/push
```

### 推送 PR 前的完整流程

```
写代码 / 修改代码
      ↓
Skill: code-simplifier:code-simplifier（清理 session 内修改）
      ↓
Skill: code-review:code-review（只输出到终端）
      ↓
根据 review 反馈修复（有问题则重复上两步）
      ↓
执行 commit + push
      ↓
Skill: code-review:code-review --comment（将 review 结果 post 到 GitHub PR 评论）
```

### 严禁的行为

- 不得以"这只是简单改动"为由跳过流程
- 不得以"用户只说了 commit/push"为由跳过流程
- 不得在未完成 simplifier + review 的情况下执行任何 commit/push 操作
- 不得在调用 commit-commands 相关 skill 之前跳过此流程

此规则适用于所有项目，无一例外。
