English | [简体中文](README.md)

# Tests

## Running Tests

### Install Dependencies

```bash
uv sync
```

### Run All Tests

```bash
uv run pytest tests/ -v
```

### Run Specific Test File

```bash
uv run pytest tests/test_auto_manager.py -v
```

### View Code Coverage

```bash
uv run pytest tests/ --cov=scripts --cov-report=html
```

Then open `htmlcov/index.html` to view the detailed coverage report.

## Test Coverage

Current tests primarily cover:

1. **Retry logic**: First failure handling and maximum retry count
2. **Plugin name validation**: Plugin name format checking
3. **Log rotation**: Seek offset calculation
4. **Notification escaping**: Special character escaping to prevent injection
5. **Git sync**: Only specific files are added to commits

## Future Improvements

- [ ] Add integration tests
- [ ] Add tests with mock subprocess calls
- [ ] Test cross-platform compatibility
- [ ] Add CI/CD configuration (GitHub Actions)
- [ ] Increase test coverage to 80%+
