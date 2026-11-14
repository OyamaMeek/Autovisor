import asyncio
import contextlib
import os
import unittest

from playwright.async_api import async_playwright

from modules.answering import AnswerError, answer_question
from modules.fusion_adapter import FusionAdapter
from modules.tasks import skip_questions


class _BrowserTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(channel="chrome", headless=True)
        self.page = await self.browser.new_page()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()


@unittest.skipUnless(os.environ.get("AUTOVISOR_TEST_BROWSER") == "1", "需要显式启用真实浏览器测试")
class BrowserAnswerTests(_BrowserTestCase):
    async def test_incomplete_fusion_question_waits_for_manual_answer_without_submitting(self):
        await self.page.set_content('''
            <div class="ai-class-exercise-dialog">
                <p>没有选项的题目</p>
                <div class="el-dialog__footer"><button class="el-button"
                    onclick="document.body.dataset.submitted = 'yes'">提交</button></div>
            </div>
        ''')
        task = asyncio.create_task(FusionAdapter.skip_ai_exercise(self.page))
        try:
            await asyncio.sleep(0.5)
            self.assertFalse(task.done())
            self.assertIsNone(await self.page.locator("body").get_attribute("data-submitted"))
            await self.page.locator(".ai-class-exercise-dialog").evaluate("el => el.remove()")
            self.assertTrue(await asyncio.wait_for(task, timeout=3))
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_legacy_monitor_does_not_close_fusion_dialog(self):
        await self.page.set_content('''
            <div class="el-dialog ai-class-exercise-dialog" tabindex="0"
                 onkeydown="this.remove()">
                <button class="option">选项</button>
            </div>
        ''')
        task = asyncio.create_task(skip_questions(self.page, asyncio.Event()))
        try:
            await asyncio.sleep(2.5)
            self.assertTrue(await self.page.locator(".ai-class-exercise-dialog").is_visible())
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@unittest.skipUnless(
    os.environ.get("AUTOVISOR_TEST_CODEX_ACP") == "1",
    "需要显式启用真实 Codex ACP 测试、安装适配器并登录",
)
class CodexAnswerTests(_BrowserTestCase):
    async def test_legacy_question_uses_codex_answer_and_closes_dialog(self):
        await self.page.set_content('''
            <div class="el-dialog" tabindex="0" onkeydown="if(event.key==='Escape') this.hidden=true">
                <div class="el-scrollbar__view"><button class="number">1</button></div>
                <p>单选题：1 + 1 等于多少？</p>
                <button class="topic-item" onclick="document.body.dataset.answer='1'">3</button>
                <button class="topic-item" onclick="document.body.dataset.answer='2'">2</button>
                <button class="topic-item" onclick="document.body.dataset.answer='3'">5</button>
            </div>
        ''')
        completed = asyncio.Event()
        task = asyncio.create_task(skip_questions(self.page, completed))
        try:
            await asyncio.wait_for(completed.wait(), timeout=135)
            self.assertEqual(await self.page.locator("body").get_attribute("data-answer"), "2")
            self.assertFalse(await self.page.locator(".el-dialog").is_visible())
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_fusion_multiple_answers_are_selected_before_submit(self):
        await self.page.set_content('''
            <div class="ai-class-exercise-dialog">
                <p>多选题：选择所有质数。</p>
                <label class="option"><input type="checkbox" value="1">4</label>
                <label class="option"><input type="checkbox" value="2">2</label>
                <label class="option"><input type="checkbox" value="3">9</label>
                <label class="option"><input type="checkbox" value="4">3</label>
                <div class="el-dialog__footer"><button class="el-button"
                    onclick="this.closest('.ai-class-exercise-dialog').hidden=true">提交</button></div>
            </div>
        ''')
        self.assertTrue(await asyncio.wait_for(FusionAdapter.skip_ai_exercise(self.page), timeout=135))
        self.assertEqual(
            await self.page.locator("input:checked").evaluate_all("els => els.map(el => el.value)"),
            ["2", "4"],
        )
        self.assertFalse(await self.page.locator(".ai-class-exercise-dialog").is_visible())

    async def test_changed_question_does_not_receive_stale_answer(self):
        await self.page.set_content('''
            <div id="question"><p>单选题：1 + 1 等于多少？</p>
                <button class="option" onclick="this.dataset.clicked='yes'">2</button>
                <button class="option" onclick="this.dataset.clicked='yes'">3</button>
            </div>
        ''')
        task = asyncio.create_task(answer_question(self.page.locator("#question"), ".option"))
        await asyncio.sleep(1)
        await self.page.locator("p").evaluate("el => el.textContent = '新的题目'")
        with self.assertRaisesRegex(AnswerError, "题目已变化"):
            await task
        self.assertEqual(await self.page.locator("[data-clicked]").count(), 0)
