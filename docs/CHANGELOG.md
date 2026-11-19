## [2026-11-14 13:41] 通过本地 Codex ACP 完成课中答题

- **需求/问题描述**：
  > 把做题部分调用本地 ACP Codex 完成答题。

- **实际实现的功能与改动**：
  - 普通课中题目、融合随堂练习共用 ACP 答题模块，替换固定选择选项的行为；校验 JSON 编号后点击，融合练习再提交。
  - 区分答案消息和服务提示；检查题目变化，限制输出长度和调用时间；失败时保留题目，等待手动作答。
  - 增加官方 ACP Python SDK、锁文件、使用说明及测试。适配器仅安装在忽略的项目运行目录，保留用户的模型和认证配置。
  - 全量测试：112 项中 107 项通过、5 项跳过，包括两项真实 Chrome 行为测试；锁文件和差异检查通过，`Autovisor.py --help` 启动检查通过。
  - 真实 ACP 握手与消息接收成功，但服务拒绝当前 `gpt-6.1-sol` 模型；用户要求保留模型、稍后自行调整。正确答题及提交的真实集成测试尚未通过，不将其计为已验证。

- **涉及文件**：
  - `modules/answering.py`、`modules/tasks.py`、`modules/fusion_adapter.py`
  - `tests/test_answering.py`、`tests/test_answering_integration.py`
  - `pyproject.toml`、`uv.lock`、`README.md`
  - `memory/agents.md`、`memory/plan.md`、`memory/progress.md`、`memory/verify.md`、`memory/gotchas.md`
  - `docs/CHANGELOG.md`

- **Git 提交**：`7f45b4e38fd3eb6c85b670b113b66c67427e7b64 feat(answering): answer course questions with local Codex ACP`，已推送 `origin/main`；本条提交记录通过后续文档提交补记。

---

## [2026-11-19 11:22] 改用 DeepSeek API 自动答题

- **需求/问题描述**
  > 做题时调用 DeepSeek API，由用户填写自己的 API Key。

- **实际实现的功能与改动**
  - 普通课中题目与融合随堂练习使用 `deepseek-flash` 获取答案。响应须正常结束，选项编号和当前题目须通过校验。Key 留空或请求失败时等待手动作答。
  - Windows 和 macOS 配置示例提供 `[deepseek] api_key`，图形界面可填写、保存和清除 Key。锁文件已移除 ACP 依赖。
  - 全量测试 114 项，111 项通过、3 项跳过。真实 Chrome 与本地 HTTP 服务验证了答题和提交路径。Tk Key 输入行为、锁文件、CLI 帮助、Python 编译与差异检查通过。线上 DeepSeek 请求需要用户的有效 Key，本次未验证。

- **涉及文件**
  - `Autovisor.py`、`GUI.py`、`config.ini.example`、`config.macos.ini.example`
  - `modules/answering.py`、`modules/configs.py`、`modules/course_playback.py`、`modules/fusion_adapter.py`、`modules/tasks.py`
  - `tests/test_answering.py`、`tests/test_answering_integration.py`、`tests/test_config.py`
  - `pyproject.toml`、`uv.lock`、`README.md`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `adf454372d27cbb8b7d691ee0d33b0e9746ed6e8 feat(answering): use DeepSeek API with a user-provided key`，已推送 `origin/main`。

---

## [2026-11-19 11:42] 支持智慧树作业考试答题

- **需求/问题描述**
  > 将现有 DeepSeek 答题兼容智慧树新版作业与考试页面。

- **实际实现的功能与改动**
  - 增加 `--answer-exam`，用户从在线学堂打开试卷，支持作业的新标签页及考试的同页跳转。复用用户提供的 DeepSeek Key，填写未作答的文本单选、多选和判断题，检查原题和勾选状态后逐题保存，交卷由用户确认。
  - 使用浏览器无障碍树读取当前题干的可访问文本，保留已有选择及需人工处理的题目。
  - 全量测试 119 项，116 项通过、3 项跳过。真实 Chrome 与本地 HTTP 服务验证答题和保存，空白 Key 时 CLI 返回退出码 2。Python 编译、Bash 语法、锁文件和差异检查通过。正式线上试卷和线上模型调用未验证。

- **涉及文件**
  - `Autovisor.py`、`modules/exam_answering.py`、`README.md`
  - `tests/test_answering.py`、`tests/test_answering_integration.py`、`tests/fixtures/exam_paper.html`
  - `memory/`、`docs/CHANGELOG.md`

- **Git 提交** `ecaac6c52bb860cc8bcaf595eaf30f3051cfbc4e feat(answering): support Zhihuishu assignments and exams`，已推送 `origin/main`。

---

## [2026-11-19 12:05] 支持智慧树学号登录

- **需求/问题描述**
  > 支持通过学校、学号和密码登录智慧树。

- **实际实现的功能与改动**
  - `[user-account]` 可以填写 `school`。程序在学号登录标签精确匹配学校全称，再提交学号和密码。学校留空时继续使用手机号登录。Windows 和 macOS 配置模板及图形配置工具均支持学校字段。
  - 真实 Chrome 验证线上公开表单的学校选择，以及本地学号与手机号的提交行为。Tk 验证保存、重读和清空学校字段。全量测试 120 项，117 项通过、3 项跳过。CLI 帮助、锁文件和差异检查通过。真实账号认证未验证。

- **涉及文件**
  - `Autovisor.py`、`modules/configs.py`、`modules/login.py`、`GUI.py`
  - `config.ini.example`、`config.macos.ini.example`、`README.md`、`tests/test_login.py`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `75e798fefb636b2d6e13a8110524da4c2f1669fd feat(login): support Zhihuishu student ID sign-in`，已推送 `origin/main`。

---

## [2026-11-19 12:18] 更新课程默认设置

- **需求/问题描述**
  > 默认不限每门课程运行时长，以 1.5 倍速静音播放。

- **实际实现的功能与改动**
  - 两份配置模板、配置加载器和图形配置工具采用相同的默认值，允许显式配置覆盖。
  - 配置回归测试与实际 Tk 控件检查通过。启用 Chrome 的全量测试共 122 项，119 项通过，线上 DeepSeek 和两项 Windows 专用用例跳过。Python 语法和差异检查通过。

- **涉及文件**
  - `config.ini.example`、`config.macos.ini.example`、`modules/configs.py`、`GUI.py`、`tests/test_configs.py`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `a0032c39cc5fbd53ee79ad52bcb3e5267aebfc4d fix(config): update course playback defaults`，已推送 `origin/main`。

---

## [2026-11-19 13:37] 修复作业考试启动超时

- **需求/问题描述**
  > Cookies 登录成功后，打开在线学堂超时，程序退出并关闭浏览器。配置中的空白网址也会产生警告。

- **实际实现的功能与改动**
  - 在线学堂导航提交后开始监听试卷。导航超时时保留浏览器，提示在原标签页手动打开在线学堂。空白课程网址直接跳过，保留非空无效网址提示。
  - 真实 Chrome 复现旧版超时，并通过延迟加载和超时后手动打开试卷的回归测试。全量测试 123 项，120 项通过、3 项跳过。Python 编译、CLI 帮助、启动脚本语法、锁文件和差异检查通过。未使用真实账号或线上试卷。

- **涉及文件**
  - `Autovisor.py`、`modules/configs.py`、`tests/test_answering_integration.py`、`tests/test_configs.py`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `77a3d27aaf776cde8ab82cbbd71a160e870ef278 fix(exam): keep browser open after campus navigation timeout`，已推送 `origin/main`。

---
