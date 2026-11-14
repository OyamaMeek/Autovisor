# 当前任务

- [x] 检查普通题目、融合练习、调用关系、依赖与本地 Codex 环境。
- [x] 添加答案校验测试并确认缺少模块时失败；补充服务提示混入答案的回归测试，确认修复前失败。
- [x] 实现 ACP 调用与两个答题入口。
- [x] 全量测试 112 项：107 项通过、5 项跳过，包含两项真实 Chrome 行为测试；锁文件与差异检查通过。
- [ ] 真实 Codex 正确答题及点击提交验证：当前账户拒绝 `gpt-6.1-sol`，用户明确选择保留该模型，稍后自行调整配置。三个真实答题用例保留为显式启用的集成测试，未声称通过。
- [ ] 更新使用说明和开发日志，提交并推送当前分支。

适配器已安装在忽略目录 `.autovisor/acp/`，不修改全局 npm 安装。当前 CLI 为 ChatGPT 登录；真实 ACP 已完成握手并收到模型不可用错误。模型与账号配置没有修改。

启动方式：`PATH="$PWD/.autovisor/acp/node_modules/.bin:$PATH" ./run_macos.sh`。真实测试指定 `CODEX_PATH=/opt/homebrew/bin/codex` 使用已有 CLI；生产环境可通过适配器官方 `CODEX_PATH` 指定 CLI。

测试输出：`.autovisor/final-tests.txt`；ACP 诊断：`.autovisor/acp-wire.txt`。均为忽略的本地记录，不提交。
