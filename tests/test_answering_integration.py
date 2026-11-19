import asyncio
import contextlib
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from playwright.async_api import async_playwright

from modules.answering import AnswerError, answer_question
from modules.fusion_adapter import FusionAdapter
from modules.tasks import skip_questions


class _DeepSeekHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.request = (self.path, self.headers["Authorization"], request)
        self.server.request_received.set()
        self.server.reply_ready.wait(timeout=10)
        body = json.dumps(self.server.reply).encode("utf-8")
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


@unittest.skipUnless(os.environ.get("AUTOVISOR_TEST_BROWSER") == "1", "需要显式启用真实浏览器测试")
class BrowserAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.addAsyncCleanup(self.playwright.stop)
        self.browser = await self.playwright.chromium.launch(channel="chrome", headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.page = await self.browser.new_page()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _DeepSeekHandler)
        self.server.status = 200
        self.server.request_received = threading.Event()
        self.server.reply_ready = threading.Event()
        self.server.reply_ready.set()
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.reply_ready.set)
        endpoint = f"http://127.0.0.1:{self.server.server_port}/chat/completions"
        endpoint_patch = patch("modules.answering.DEEPSEEK_API_URL", endpoint)
        endpoint_patch.start()
        self.addCleanup(endpoint_patch.stop)

    def set_answers(self, answers):
        self.server.reply = {"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"answers": answers}),
        }}]}

    async def _check_fusion_manual_answer(self, api_key):
        await self.page.set_content('''
            <div class="ai-class-exercise-dialog">
                <p>单选题：1 + 1 等于多少？</p>
                <button class="option" onclick="this.dataset.clicked='yes'">2</button>
                <button class="option" onclick="this.dataset.clicked='yes'">3</button>
                <div class="el-dialog__footer"><button class="el-button"
                    onclick="document.body.dataset.submitted = 'yes'">提交</button></div>
            </div>
        ''')
        task = asyncio.create_task(FusionAdapter.skip_ai_exercise(self.page, api_key))
        try:
            await asyncio.sleep(0.5)
            self.assertFalse(task.done())
            self.assertEqual(await self.page.locator("[data-clicked]").count(), 0)
            self.assertIsNone(await self.page.locator("body").get_attribute("data-submitted"))
            await self.page.locator(".ai-class-exercise-dialog").evaluate("el => el.remove()")
            self.assertTrue(await asyncio.wait_for(task, timeout=3))
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_missing_key_keeps_fusion_question_open_without_request(self):
        await self._check_fusion_manual_answer("")
        self.assertFalse(self.server.request_received.is_set())

    async def test_failed_authentication_keeps_fusion_question_open(self):
        self.server.status = 401
        self.server.reply = {"error": {"message": "Invalid API key"}}
        await self._check_fusion_manual_answer("key-for-test")
        self.assertTrue(self.server.request_received.is_set())

    async def test_unfinished_response_keeps_fusion_question_open(self):
        self.set_answers([1])
        self.server.reply["choices"][0]["finish_reason"] = "length"
        await self._check_fusion_manual_answer("key-for-test")
        self.assertTrue(self.server.request_received.is_set())

    async def test_legacy_monitor_does_not_close_fusion_dialog(self):
        await self.page.set_content('''
            <div class="el-dialog ai-class-exercise-dialog" tabindex="0"
                 onkeydown="this.remove()">
                <button class="option">选项</button>
            </div>
        ''')
        task = asyncio.create_task(skip_questions(self.page, asyncio.Event(), ""))
        try:
            await asyncio.sleep(2.5)
            self.assertTrue(await self.page.locator(".ai-class-exercise-dialog").is_visible())
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_legacy_question_uses_deepseek_answer_and_closes_dialog(self):
        self.set_answers([2])
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
        task = asyncio.create_task(skip_questions(self.page, completed, "key-for-test"))
        try:
            await asyncio.wait_for(completed.wait(), timeout=10)
            self.assertEqual(await self.page.locator("body").get_attribute("data-answer"), "2")
            self.assertFalse(await self.page.locator(".el-dialog").is_visible())
            path, authorization, request = self.server.request
            self.assertEqual(path, "/chat/completions")
            self.assertEqual(authorization, "Bearer key-for-test")
            self.assertEqual(request["model"], "deepseek-flash")
            self.assertEqual(request["response_format"], {"type": "json_object"})
            question = json.loads(request["messages"][1]["content"])
            self.assertIn("1 + 1", question["question"])
            self.assertEqual(question["options"], ["3", "2", "5"])
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_fusion_multiple_answers_are_selected_before_submit(self):
        self.set_answers([2, 4])
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
        self.assertTrue(await asyncio.wait_for(FusionAdapter.skip_ai_exercise(self.page, "key-for-test"), timeout=10))
        self.assertEqual(
            await self.page.locator("input:checked").evaluate_all("els => els.map(el => el.value)"),
            ["2", "4"],
        )
        self.assertFalse(await self.page.locator(".ai-class-exercise-dialog").is_visible())

    async def test_changed_question_does_not_receive_stale_answer(self):
        self.set_answers([1])
        self.server.reply_ready.clear()
        await self.page.set_content('''
            <div id="question"><p>单选题：1 + 1 等于多少？</p>
                <button class="option" onclick="this.dataset.clicked='yes'">2</button>
                <button class="option" onclick="this.dataset.clicked='yes'">3</button>
            </div>
        ''')
        task = asyncio.create_task(answer_question(self.page.locator("#question"), ".option", "key-for-test"))
        try:
            self.assertTrue(await asyncio.to_thread(self.server.request_received.wait, 5))
            await self.page.locator("p").evaluate("el => el.textContent = '新的题目'")
            self.server.reply_ready.set()
            with self.assertRaisesRegex(AnswerError, "题目已变化"):
                await asyncio.wait_for(task, timeout=5)
            self.assertEqual(await self.page.locator("[data-clicked]").count(), 0)
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
