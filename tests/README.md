# Tests

## 运行测试

### 安装依赖

```bash
pip install pytest pytest-cov
```

### 运行所有测试

```bash
pytest tests/ -v
```

### 运行特定测试文件

```bash
pytest tests/test_auto_manager.py -v
```

### 查看代码覆盖率

```bash
pytest tests/ --cov=scripts --cov-report=html
```

然后打开 `htmlcov/index.html` 查看详细的覆盖率报告。

## 测试说明

当前测试主要覆盖：

1. **重试逻辑**：验证首次失败和最大重试次数
2. **插件名称验证**：验证插件名格式检查
3. **日志轮转**：验证 seek 偏移量计算
4. **通知转义**：验证特殊字符转义防止注入
5. **Git 同步**：验证只添加特定文件

## 未来改进

- [ ] 添加集成测试
- [ ] 添加 mock subprocess 调用的测试
- [ ] 测试跨平台兼容性
- [ ] 添加 CI/CD 配置（GitHub Actions）
- [ ] 提高测试覆盖率到 80%+
