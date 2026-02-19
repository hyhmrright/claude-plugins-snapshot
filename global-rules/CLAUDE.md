# 全局开发规则

## 代码改动流程（必须遵守）

### 日常开发循环

每次完成代码改动后，必须按以下流程执行，循环直到无问题为止：

1. **code-simplifier**：对刚改动的代码进行简化和优化（自动触发，聚焦 session 内修改）
2. **`/code-review`**：对优化后的代码进行审查（只输出到终端，不发 GitHub 评论）
3. **如果 review 发现问题**：修复问题，回到第 1 步
4. **如果 review 无问题**：流程结束，可以提交

```
改动代码 → code-simplifier → /code-review → 有问题？ → 是 → 修复 → 回到 code-simplifier
                                              ↓
                                              否 → 完成，可以提交
```

### 推送 PR 前的完整流程

```
写代码 / 修改代码
      ↓
【code-simplifier】自动运行，清理刚写完的代码
      ↓
推送 PR 前："Use the code-simplifier to clean up these changes"
（此时 code-simplifier 会分析 git diff，清理所有待提交变更）
      ↓
【/code-review】在 PR 分支上运行完整审查（只输出到终端）
      ↓
根据 review 反馈修复
      ↓
/code-review --comment   # 将最终 review 结果 post 到 GitHub PR 评论
```

此规则适用于所有项目，无一例外。
