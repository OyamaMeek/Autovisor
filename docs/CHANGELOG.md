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

## [2026-11-19 14:08] 作业答完后自动暂存

- **需求/问题描述**
  > 答完作业后点击「暂存作业」并确认。

- **实际实现的功能与改动**
  - 保存末题后，作业页面完成率达到 100% 时点击「暂存作业」，并在暂存确认框中点击「确定」。未完成的作业留在答题页，交卷由用户操作。
  - Chrome 回归测试覆盖末题保存、已有选项、未完成作业和确认后关闭标签页。全量测试 127 项，124 项通过、3 项跳过。Python 编译、CLI 帮助和差异检查通过。暂存行为使用本地作业页面验证。

- **涉及文件**
  - `modules/exam_answering.py`、`Autovisor.py`、`README.md`、`tests/test_answering_integration.py`、`tests/fixtures/exam_paper.html`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `a9541f8aab0a768f301edb53f7d4a7a705f7bc2a feat(exam): stash completed homework`，已推送 `origin/main`。

---

## [2026-11-19 14:25] 逐份打开未提交的作业

- **需求/问题描述**
  > 将自动逐份打开作业写进脚本。

- **实际实现的功能与改动**
  - 在 `--answer-exam` 模式中选择课程并进入「未提交」列表后，脚本按顺序点击可答作业的「开始答题」，等待答题标签页跳转，并复用现有作答与暂存流程。通过列表网址和卡片信息避免重复打开。考试试卷由用户手动打开，交卷由用户操作。
  - 本地 Chrome 回归验证多份作业依次打开、列表重建后去重、暂存关闭标签页以及交卷边界。全量测试 128 项，125 项通过、3 项跳过。最终版本的作业列表回归、Python 编译、CLI 帮助和差异检查通过。未运行线上作业。

- **涉及文件**
  - `modules/exam_answering.py`、`Autovisor.py`、`README.md`、`tests/test_answering_integration.py`、`tests/fixtures/exam_paper.html`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `d38bfcf15451f05463e4a220358644bea35e8a5b feat(exam): open unsubmitted homework in order`，已推送 `origin/main`。

---

## [2026-11-19 14:33] 保存 DeepSeek 答案到本地 Markdown

- **需求/问题描述**
  > 把每次调用 DeepSeek 的答案保存到本地 Markdown。

- **实际实现的功能与改动**
  - 课中题、融合练习和作业考试共用的 DeepSeek 入口将每次通过校验的答案追加到 `.autovisor/deepseek-answers.md`，每条包含时间、题目、选项和答案。写入失败时提示，已校验的答案仍可用于作答。
  - 本地 HTTP 和真实文件验证连续追加、中文及多选答案、无效答案处理和写入失败。启用 Chrome 的全量测试共 130 项，127 项通过、3 项跳过。最终版本的 5 项专项回归、Python 编译、CLI 帮助和差异检查通过。线上 DeepSeek 请求未执行。

- **涉及文件**
  - `modules/answering.py`、`tests/test_answering_integration.py`、`README.md`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `4e0c6844cdfe0be1e53cbc8f389cf0553b101c03 feat(answering): save DeepSeek answers to Markdown`，已推送 `origin/main`。

---

## [2026-11-19 14:55] 首题加载超时后刷新试卷

- **需求/问题描述**
  > 作业或试卷的题目加载不出来时需要重新加载，并核对日志里的保存失败提示。

- **实际实现的功能与改动**
  - 等待首题 15 秒超时后刷新当前试卷一次。平台验证和作答阶段的异常保留当前页面。自动刷新后仍未加载时，手动刷新让题目显示后可恢复。
  - 本地日志中的作答异常对应点击后未检测到勾选状态，发生在保存步骤之前。未验证线上页面未显示勾选的原因。
  - 启用 Chrome 的全量测试共 133 项，130 项通过、3 项跳过。Python 编译、CLI 帮助和差异检查通过。

- **涉及文件**
  - `modules/exam_answering.py`、`tests/test_answering_integration.py`、`README.md`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `c206f8711d75a32ddd19035e0e6442bf684cf13d fix(exam): reload when the first question fails to load`，已推送 `origin/main`。

---

## [2026-11-19 15:06] 修复作业选项识别与窗口顺序

- **需求/问题描述**
  > 修复作业打开和答题阶段的警告，每次只打开一份作业。

- **实际实现的功能与改动**
  - 识别页面高亮和输入框勾选两种已选状态，保留用户选择并确认自动选择后继续保存。
  - 当前作业窗口未关闭时暂停打开下一份。空白窗口超时后仍继续监听，并区分未打开窗口和未进入答题页的提示。
  - 真实 Chrome 专项回归 3 项全部通过。启用 Chrome 的全量测试 133 项，130 项通过、3 项跳过。Python 编译、CLI 帮助和差异检查通过。未运行线上试卷。

- **涉及文件**
  - `modules/exam_answering.py`、`Autovisor.py`、`README.md`
  - `tests/fixtures/exam_paper.html`、`tests/test_answering_integration.py`
  - `memory/`、`docs/CHANGELOG.md`

- **Git 提交** `103f560b1964006011b160907956b5df5f057be0 fix(exam): wait for each homework window to close`，已推送 `origin/main`。

---

## [2026-11-19 15:47] 题目变化后自动重新作答

- **需求/问题描述**
  > 作答期间检测到题目或选择变化时，自动重新作答。

- **实际实现的功能与改动**
  - 丢弃失效的答案，重新读取同一份试卷上的当前题，对未勾选题目重新请求 DeepSeek，保留已有选择。连续变化时最多重试三次。
  - 真实 Chrome 和本地 HTTP 服务验证重试后保存新答案、保留手动勾选和重试上限。全量测试 135 项，132 项通过、3 项跳过。Python 语法、CLI 帮助和差异检查通过。未运行线上试卷。

- **涉及文件**
  - `modules/exam_answering.py`、`tests/test_answering_integration.py`、`README.md`
  - `memory/plan.md`、`memory/progress.md`、`memory/verify.md`、`docs/CHANGELOG.md`

- **Git 提交** `045e46c4c8529f400bb75d52abd77f509dc06fb6 fix(exam): retry when the current question changes`，已推送 `origin/main`。

---

## [2026-11-19 16:07] 自动构建 Windows 发行包

- **需求/问题描述**
  > 发布当前版本，并由 GitHub Actions 自动构建和上传 Windows 发行包。

- **实际实现的功能与改动**
  - 将程序版本设为 `3.19.0`，下载和更新检查指向 `OyamaMeek/Autovisor` 的 Releases。
  - 推送版本标签后，在 Windows x64 校验版本并运行测试，构建 ZIP，解压核对配置、许可证和运行依赖，运行 `Autovisor.exe --help` 后发布。
  - 本地启用 Chrome 的全量测试 135 项，132 项通过、3 项跳过。actionlint、依赖锁、PyInstaller 版本解析、源码 CLI 帮助、Python 语法和差异检查通过。
  - 首轮 Windows 测试和构建通过，发行包在重定向输出时打印中文帮助失败，因此未创建 `3.19.0` Release。

- **涉及文件**
  - `.github/workflows/release.yml`、`build.py`、`modules/version.py`、`modules/updater.py`、`README.md`
  - `memory/plan.md`、`memory/progress.md`、`memory/verify.md`、`docs/CHANGELOG.md`

- **Git 提交** `ef045ac07d86e24f3bf222b4f87d6225bd6744f7 feat(release): automate Windows builds for version tags`，已推送 `origin/main`。

---

## [2026-11-19 16:11] 修复 Windows 发行包的中文输出

- **需求/问题描述**
  > Windows 发行包在重定向 `Autovisor.exe --help` 输出时，CP1252 无法编码中文，工作流终止发布。

- **实际实现的功能与改动**
  - 在 PyInstaller 内嵌的解释器启用 UTF-8。`3.19.1` 已发布至 `OyamaMeek/Autovisor`。
  - Windows Actions 运行 `44485741541` 成功，135 项测试中 131 项通过、4 项跳过，解压后的 `Autovisor.exe --help` 可输出中文。macOS Apple Silicon 和 Intel 冒烟测试通过。
  - 从公开下载地址取回 ZIP，SHA-256 与 GitHub 一致，压缩包完整，主程序为 Windows x86-64。更新接口返回 `3.19.1`。

- **涉及文件**
  - `build.py`、`modules/version.py`、`README.md`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `f77b0eb80223208652db8987ad35b5b10fec507b fix(release): enable UTF-8 in the packaged runtime`，已推送 `origin/main`。

---

## [2026-11-19 16:29] 更新 Autovisor 维护者信息

- **需求/问题描述**
  > 移除原作者的个人信息，将项目维护者署名改为 OyamaMeek。

- **实际实现的功能与改动**
  - README 和启动界面显示 `OyamaMeek`。移除旧仓库链接、个人公告、博客和赞赏码，保留 MIT 许可证要求的原始版权声明。
  - 删除赞赏码显示逻辑、配置模板字段、Windows 打包引用和仅用于显示赞赏码的 Pillow 依赖。旧配置仍可读取。
  - 启用 Chrome 的全量测试 135 项，132 项通过、3 项跳过。更新锁文件后，独立环境的默认测试套件、CLI 启动与帮助、Python 编译、`actionlint` 和差异检查通过。本次未生成新的 Windows 发行包。

- **涉及文件**
  - `README.md`、`Autovisor.py`、`modules/banner.py`、`modules/configs.py`、`modules/support.py`
  - `config.ini.example`、`config.macos.ini.example`、`resources/`、`.gitignore`、`build.py`、`.github/workflows/release.yml`
  - `pyproject.toml`、`uv.lock`、`tests/`、`memory/`、`docs/CHANGELOG.md`

- **Git 提交** `741481d05ba6895a5b6a48a63f5e214f0798b6d1 chore: update project maintainer attribution`，已推送 `origin/main`。

---
