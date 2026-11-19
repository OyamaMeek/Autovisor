# 当前环境

- Python 3.13、uv、Playwright；现有测试使用 unittest。
- 本次使用 ponytail 技能；不使用子代理，不进行截图或视觉检查。
- 答题改用 DeepSeek Chat Completions API，复用项目已有的 httpx 异步客户端，模型为 `deepseek-flash`。
- 作业考试模式通过 Playwright 操作浏览器原生控件，通过 Chromium 无障碍树读取当前题干的可访问文本。
- 学号登录复用 Python `Config`、Playwright 和 Tk 图形配置工具，使用学校下拉列表和智慧树登录表单。
