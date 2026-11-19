# 验证标准

- 验证旧配置、空白 Key 与已填写 Key；检查无 Key 时保留题目供手动完成。
- 运行答案校验及真实本地 HTTP、Chrome 测试，检查请求格式、单选、多选、认证失败和等待期间题目变化的处理。
- 使用 `AUTOVISOR_TEST_BROWSER=1 uv run python -m unittest discover -s tests -v` 运行测试套件。使用用户提供的有效 Key 时，可单独验证 DeepSeek 服务返回真实答案。
- 运行 `uv lock --check`、`uv run python Autovisor.py --help` 与 `git diff --check`，确认凭证未进入提交。

## 2026-11-19 结果

- 在按锁文件创建的独立环境中运行 114 项测试，111 项通过、3 项跳过。真实 Chrome 和本地 HTTP 覆盖正常作答、融合提交、缺少 Key、认证失败、响应截断与题目变化。
- 真实 Tk 控件在隔离配置目录中通过 Key 的掩码、保存、重读与清空检查。
- 锁文件、CLI 帮助、Python 编译和差异检查均通过。
- 当前环境缺少用户的有效 DeepSeek Key，线上答题验证跳过。另外两项跳过的是 Windows 专用测试。
