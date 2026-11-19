import asyncio
import contextlib
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playwright.async_api import async_playwright

from Autovisor import run_exam_mode
from modules.answering import AnswerError, answer_question
from modules.browser import BrowserSession
from modules.exam_answering import fill_exam
from modules.fusion_adapter import FusionAdapter
from modules.logger import Logger
from modules.tasks import skip_questions


class _DeepSeekHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.request = (self.path, self.headers["Authorization"], request)
        self.server.request_received.set()
        self.server.reply_ready.wait(timeout=10)
        reply = self.server.reply(request) if callable(self.server.reply) else self.server.reply
        body = json.dumps(reply).encode("utf-8")
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

    async def _serve_exam(self, route="dohomework", query=""):
        base_url = "https://onlineexamh5new.zhihuishu.com/stuExamWeb.html"
        exam = Path(__file__).with_name("fixtures") / "exam_paper.html"
        await self.page.context.route(base_url + "*", lambda request_route: request_route.fulfill(path=exam))
        params = "recruit/work/exam/course/school" + ("/0" if route == "dohomework" else "")
        return f"{base_url}{query}#/webExamList/{route}/{params}"

    def _start_exam_mode(self):
        session = BrowserSession(self.browser, self.page.context, self.page, attached=True)
        config = SimpleNamespace(attach_existing_chrome=True, deepseek_api_key="key-for-test")

        async def run():
            with patch("Autovisor.create_browser_session", return_value=session), patch(
                "Autovisor.logger", Logger(), create=True
            ):
                await run_exam_mode(config)

        return asyncio.create_task(run())

    async def test_exam_waits_for_manually_opened_paper_and_saves_without_submitting(self):
        url = await self._serve_exam()
        statements = []

        def reply(request):
            data = json.loads(request["messages"][1]["content"])
            statements.append(data["question"])
            answers = [1, 3] if "质数" in data["question"] and "多选题" in data["question"] else [2]
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"answers": answers})}}]}

        self.server.reply = reply
        campus_url = "https://onlineweb.zhihuishu.com/onlinestuh5"
        script_release = asyncio.Event()

        async def hold_script(route):
            await script_release.wait()
            await route.fulfill(body="")

        await self.page.route(campus_url + "/slow.js", hold_script)
        await self.page.route(campus_url, lambda route: route.fulfill(
            content_type="text/html; charset=utf-8",
            body=f'<button onclick="window.open(\'{url}\')">开始答题</button>'
                 f'<script src="{campus_url}/slow.js"></script>',
        ))
        task = self._start_exam_mode()
        try:
            start_button = self.page.get_by_role("button", name="开始答题")
            await start_button.wait_for(timeout=5000)
            self.assertEqual(await self.page.evaluate("document.readyState"), "loading")
            self.assertFalse(self.server.request_received.is_set())
            async with self.page.expect_popup(timeout=5000) as popup:
                await start_button.click()
            paper = await popup.value
            await paper.get_by_text("保存成功！", exact=True).wait_for(timeout=12000)
            body = paper.locator("body")
            self.assertEqual(await body.get_attribute("data-saved0"), "1")
            self.assertEqual(await body.get_attribute("data-saved1"), "1,3")
            self.assertEqual(await body.get_attribute("data-saved2"), "")
            self.assertEqual(await body.get_attribute("data-saved3"), "2")
            self.assertIsNone(await body.get_attribute("data-submitted"))
            self.assertEqual(len(statements), 2)
            self.assertIn("选择所有质数", statements[0])
            self.assertIn("九是质数", statements[1])
        finally:
            script_release.set()
            await self.page.unroute_all(behavior="wait")
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_completed_homework_confirms_stash_after_saving_last_answer(self):
        self.set_answers([2])
        url = await self._serve_exam(query="?kind=single")
        await self.page.goto(url)

        self.assertEqual(await fill_exam(self.page, "key-for-test"), (1, 0))

        body = self.page.locator("body")
        self.assertEqual(await body.get_attribute("data-saved0"), "2")
        self.assertEqual(await body.get_attribute("data-stashed"), "2")
        self.assertIsNone(await body.get_attribute("data-submitted"))

    async def test_homework_saves_existing_selection_on_last_question_before_stashing(self):
        await self.page.goto(await self._serve_exam(query="?kind=single"))
        await self.page.get_by_text("3", exact=True).click()

        self.assertEqual(await fill_exam(self.page, "key-for-test"), (0, 0))

        self.assertEqual(await self.page.locator("body").get_attribute("data-stashed"), "1")
        self.assertFalse(self.server.request_received.is_set())

    async def test_incomplete_homework_remains_open_for_manual_review(self):
        self.set_answers([2])
        await self.page.goto(await self._serve_exam())

        self.assertEqual(await fill_exam(self.page, "key-for-test"), (2, 1))

        self.assertIsNone(await self.page.locator("body").get_attribute("data-stashed"))
        self.assertFalse(await self.page.get_by_role("dialog").is_visible())

    async def test_homework_tab_can_close_after_stash_confirmation(self):
        self.set_answers([2])
        url = await self._serve_exam(query="?kind=single")
        async with self.page.expect_popup() as popup:
            await self.page.evaluate("url => { window.open(url); }", url)
        paper = await popup.value
        await paper.wait_for_url(url)

        async with paper.expect_event("close", timeout=5000):
            self.assertEqual(await fill_exam(paper, "key-for-test"), (1, 0))

    async def test_exam_mode_tracks_paper_in_same_tab_after_campus_timeout(self):
        self.set_answers([2])
        url = await self._serve_exam("doexamination", "?kind=single")
        request_started = asyncio.Event()
        request_release = asyncio.Event()

        async def hold_campus(route):
            request_started.set()
            await request_release.wait()
            await route.abort()

        await self.page.route("https://onlineweb.zhihuishu.com/onlinestuh5", hold_campus)
        task = self._start_exam_mode()
        try:
            await asyncio.wait_for(request_started.wait(), timeout=5)
            done, _ = await asyncio.wait({task}, timeout=31)
            if done:
                await task
                self.fail("在线学堂导航超时后停止了试卷监听")
            await self.page.goto(url)
            await self.page.get_by_text("保存成功！", exact=True).wait_for(timeout=10000)
            self.assertEqual(await self.page.locator("body").get_attribute("data-saved0"), "2")
            self.assertIsNone(await self.page.locator("body").get_attribute("data-submitted"))
        finally:
            if not self.page.is_closed():
                await self.page.unroute_all(behavior="ignoreErrors")
            request_release.set()
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_exam_rejects_multiple_answers_on_single_choice(self):
        self.set_answers([1, 2])
        url = await self._serve_exam("doexamination", "?kind=single")
        await self.page.goto(url)
        with self.assertRaisesRegex(AnswerError, "单选"):
            await fill_exam(self.page, "key-for-test")
        self.assertEqual(await self.page.locator("input:checked").count(), 0)
        self.assertIsNone(await self.page.locator("body").get_attribute("data-saved0"))

    async def test_exam_keeps_selection_made_by_user_during_request(self):
        self.set_answers([2])
        self.server.reply_ready.clear()
        url = await self._serve_exam("doexamination", "?kind=single")
        await self.page.goto(url)
        task = asyncio.create_task(fill_exam(self.page, "key-for-test"))
        try:
            self.assertTrue(await asyncio.to_thread(self.server.request_received.wait, 5))
            await self.page.locator(".nodeLab").first.click()
            self.server.reply_ready.set()
            with self.assertRaisesRegex(AnswerError, "已变化"):
                await asyncio.wait_for(task, timeout=5)
            self.assertEqual(await self.page.locator("input:checked").input_value(), "1")
            self.assertIsNone(await self.page.locator("body").get_attribute("data-saved0"))
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
