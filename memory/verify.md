# 验证标准

- 答案 JSON 校验覆盖多选、判断题、空答案、重复/越界/非整数编号、无效 JSON。
- 全量：`uv run python -m unittest discover -s tests -v`。
- 真实 ACP：通过已登录的 Codex 返回答案；通过 Playwright 的真实浏览器执行选项点击和融合提交，核对 DOM 结果，不截图。
- 检查失败时不会继续提交猜测答案；核对调用超时与任务取消的资源清理。
- `git diff --check`；仅提交任务文件，不包含配置凭证、缓存或日志。

## 2026-11-14 结果

- 全量测试启用 `AUTOVISOR_TEST_BROWSER=1`：112 项中 107 项通过、5 项跳过（3 项真实 Codex 答题、2 项原有平台相关测试）。
- Chrome 实际验证：不完整题目不会提交，手动关闭后继续；普通答题监控不会关闭融合弹窗。
- ACP 实际完成初始化、会话建立、请求与消息接收；服务返回 `gpt-6.1-sol` 不支持当前 ChatGPT 账户，无法验证正确答案与自动提交。用户要求保留模型配置。
- SDK 1.0.0 负责连接及子进程关闭，具备分阶段终止超时；没有单独验证长时间推理超时和强制终止场景。
- `uv lock --check`、`git diff --check`、`uv run python Autovisor.py --help` 通过。没有配置独立类型检查或 lint，不新增检查工具。
