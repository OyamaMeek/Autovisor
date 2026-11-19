import asyncio
import configparser
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

from playwright.async_api import async_playwright

import Autovisor
from modules.configs import Config
from modules.login import is_login_page
from modules.slider import image_to_display_point
from Autovisor import init_page


class LoginUrlTests(unittest.TestCase):
    def test_recognizes_current_and_legacy_login_hosts(self):
        self.assertTrue(is_login_page("https://login.zhihuishu.com/?origin=zhs"))
        self.assertTrue(is_login_page("https://passport.zhihuishu.com/login"))

    def test_rejects_authenticated_destination_hosts(self):
        self.assertFalse(is_login_page("https://www.zhihuishu.com/"))
        self.assertFalse(is_login_page("https://onlineweb.zhihuishu.com/"))

    def test_does_not_match_login_text_outside_the_hostname(self):
        self.assertFalse(is_login_page("https://example.com/login.zhihuishu.com"))

    def test_converts_opencv_point_to_display_coordinates(self):
        self.assertEqual(
            image_to_display_point((240, 120), 480, 240, 400, 200),
            (200, 100),
        )

    def test_browser_starts_maximized(self):
        args = init_page.__code__.co_consts
        self.assertIn("--start-maximized", args)
        self.assertIn("--window-position=0,0", args)
        self.assertIn(("viewport",), args)


@unittest.skipUnless(os.environ.get("AUTOVISOR_TEST_BROWSER") == "1", "需要显式启用真实浏览器测试")
class BrowserLoginTests(unittest.IsolatedAsyncioTestCase):
    async def test_configured_school_submits_student_form_and_old_config_submits_phone_form(self):
        form = """
            <div role="tab" id="tab-2" onclick="
                phone.hidden = phone.disabled = true;
                student.hidden = unid.disabled = false;
            ">学号登录</div>
            <form method="post" action="https://onlineweb.zhihuishu.com/">
                <input id="phone" name="mobile">
                <div id="student" hidden>
                    <input role="combobox" oninput="schools.hidden = this.value !== '浙江大学'">
                    <div id="schools" role="listbox" hidden>
                        <div role="option">浙江大学医学院</div>
                        <div role="option" onclick="school.value = this.textContent.trim(); schools.hidden = true">
                            浙江大学</div>
                    </div>
                    <input id="school" name="school" type="hidden">
                    <input id="unid" name="unid" disabled>
                </div>
                <input name="password" type="password">
                <input name="agree" value="yes" type="checkbox" class="el-checkbox__original" hidden>
                <button type="submit">登录</button>
            </form>
        """
        repo = Path(__file__).resolve().parents[1]
        playwright = await async_playwright().start()
        self.addAsyncCleanup(playwright.stop)
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        self.addAsyncCleanup(browser.close)
        for school, account, expected in (
            ("浙江大学", "0012345", {"school": ["浙江大学"], "unid": ["0012345"]}),
            ("", "13800000000", {"mobile": ["13800000000"]}),
        ):
            with self.subTest(school=school), tempfile.TemporaryDirectory() as directory:
                config_path = Path(directory) / "config.ini"
                ini = configparser.ConfigParser()
                ini.read(repo / "config.ini.example", encoding="utf-8")
                ini["course-url"] = {}
                ini["user-account"] = {"username": account, "password": "test-password"}
                if school:
                    ini["user-account"]["school"] = school
                with config_path.open("w", encoding="utf-8") as file:
                    ini.write(file)
                config = Config(config_path, repo / "data/mirrors.json")
                page = await browser.new_page()
                self.addAsyncCleanup(page.context.close)
                await page.route("**/*", lambda route: route.abort())
                await page.route(config.login_url, lambda route: route.fulfill(
                    body=form, content_type="text/html; charset=utf-8"
                ))
                await page.route("https://onlineweb.zhihuishu.com/", lambda route: route.fulfill(body="received"))
                with patch.object(Autovisor, "logger", Autovisor.Logger(), create=True):
                    async with page.expect_request("https://onlineweb.zhihuishu.com/", timeout=5000) as request:
                        await asyncio.wait_for(Autovisor.auto_login(page.context, page, config), timeout=5)
                self.assertEqual(parse_qs((await request.value).post_data), {
                    **expected, "password": ["test-password"], "agree": ["yes"],
                })


if __name__ == "__main__":
    unittest.main()
