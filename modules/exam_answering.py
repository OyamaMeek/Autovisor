import asyncio
import json
from collections import Counter
from unicodedata import category
from urllib.parse import urlsplit

from playwright.async_api import CDPSession, Error as PlaywrightError, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from modules.answering import AnswerError, ask_deepseek
from modules.logger import Logger
from modules.tasks import has_visible_verification

logger = Logger()
PAPER_LOAD_TIMEOUT_MS = 15000
QUESTION_CHANGE_RETRIES = 3
QUESTION = ".examPaper_box .examPaper_subject"
ANCHOR = "> .subject_stem .subject_num [id^='anchor_']"
STEM = "> .subject_stem .subject_describe"
KIND = "> .subject_stem .subject_type > span:first-child"
CHOICES = ".subject_node .nodeLab:visible"
OPTION_TEXT = ".node_detail"
SELECTED_OPTION = f"input:checked, {OPTION_TEXT}.onChecked"
MEDIA = "img:visible, canvas:visible, video:visible, audio:visible"


class _QuestionChanged(AnswerError):
    pass


def is_exam_paper_url(url: str) -> bool:
    parsed = urlsplit(url)
    route = parsed.fragment.split("?", 1)[0].split("/")
    return (
        parsed.scheme == "https"
        and parsed.netloc == "onlineexamh5new.zhihuishu.com"
        and parsed.path == "/stuExamWeb.html"
        and route[:2] == ["", "webExamList"]
        and ((len(route) == 9 and route[2] == "dohomework") or (len(route) == 8 and route[2] == "doexamination"))
        and all(route[3:])
    )


async def _read_stem(cdp: CDPSession, selector: str) -> str:
    # 普通 DOM Locator 读不到封闭 Shadow DOM，题干也可通过浏览器无障碍树读取。
    document = await cdp.send("DOM.getDocument", {"depth": 0})
    node = await cdp.send("DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": selector})
    if not node["nodeId"]:
        return ""
    tree = await cdp.send("Accessibility.queryAXTree", {"nodeId": node["nodeId"]})
    displayed = [item for item in tree["nodes"] if not item["ignored"]]
    if any(item["role"]["value"] in {"image", "Canvas", "Video", "Audio"} for item in displayed):
        return ""
    return " ".join(
        item["name"]["value"] for item in displayed if item["role"]["value"] == "StaticText"
    ).strip()


async def _fill_current_question(page: Page, cdp: CDPSession, selector: str, api_key: str) -> tuple[int, int]:
    url = page.url
    question = page.locator(f"{selector}:visible")
    choices = question.locator(CHOICES)
    selected_choices = choices.filter(has=page.locator(SELECTED_OPTION))
    if await selected_choices.count():
        return 0, 0
    kind = (await question.locator(KIND).inner_text(timeout=2500)).strip("【】 \r\n")
    if kind not in {"单选题", "多选题", "判断题"}:
        return 0, 1
    content = choices.locator(OPTION_TEXT)
    options = [text.strip() for text in await content.all_inner_texts()]
    stem = await _read_stem(cdp, f"{selector} {STEM}")
    if (
        not stem or len(options) < 2 or len(options) != await choices.count()
        or any(not option for option in options)
        or any(category(char) == "Co" for char in stem + "".join(options))
        or await question.locator(STEM).locator(MEDIA).count()
        or await content.locator(MEDIA).count()
    ):
        return 0, 1

    answers = await ask_deepseek(f"{kind}：{stem}", options, api_key)
    if (
        page.url != url or not await question.is_visible() or await selected_choices.count()
        or [text.strip() for text in await content.all_inner_texts()] != options
        or await _read_stem(cdp, f"{selector} {STEM}") != stem
    ):
        raise _QuestionChanged
    if kind != "多选题" and len(answers) != 1:
        raise AnswerError("单选题和判断题只允许填写一个选项")
    if await has_visible_verification(page):
        raise AnswerError("检测到平台验证，请在浏览器手动处理")
    for index in answers:
        choice = choices.nth(index)
        await choice.click(timeout=2500)
        await choice.locator(SELECTED_OPTION).first.wait_for(state="attached", timeout=2500)
    selected = await choices.evaluate_all(
        "(rows, selector) => rows.flatMap((row, index) => row.querySelector(selector) ? [index] : [])",
        SELECTED_OPTION,
    )
    if selected != sorted(answers):
        raise AnswerError("页面选中状态与返回的答案不一致")
    return 1, 0


async def fill_exam(page: Page, api_key: str) -> tuple[int, int]:
    url = page.url
    if not is_exam_paper_url(url):
        raise AnswerError("当前页面不是受支持的作业考试答题页")
    if not api_key:
        raise AnswerError("请在配置文件的 [deepseek] 中填写 api_key")

    visible_anchor = page.locator(f"{QUESTION}:visible {ANCHOR}:visible")
    controls = page.locator(".examPaper_box .switch-btn-box:visible")
    next_button = controls.get_by_role("button", name="下一题", exact=True)
    save_button = controls.get_by_role("button", name="保存", exact=True)
    stash_button = page.get_by_role("button", name="暂存作业", exact=True)
    filled = skipped = retries = 0
    cdp = await page.context.new_cdp_session(page)
    try:
        while page.url == url:
            if await has_visible_verification(page):
                raise AnswerError("检测到平台验证，请在浏览器手动处理")
            anchor = await visible_anchor.get_attribute("id", timeout=10000)
            if page.url != url:
                break
            selector = f"{QUESTION}:has({ANCHOR}[id={json.dumps(anchor, ensure_ascii=False)}])"
            try:
                result, needs_manual = await _fill_current_question(page, cdp, selector, api_key)
            except _QuestionChanged:
                if page.url != url:
                    break
                if retries == QUESTION_CHANGE_RETRIES:
                    raise AnswerError("题目或选择持续变化，已达到自动重试上限") from None
                retries += 1
                logger.info(f"题目或选择已变化，正在重新读取当前题（{retries}/{QUESTION_CHANGE_RETRIES}）。", shift=True)
                continue
            retries = 0
            filled += result
            skipped += needs_manual
            if page.url != url or not await page.locator(f"{selector}:visible").is_visible():
                raise AnswerError("当前题目已变化，已暂停答题")
            if await has_visible_verification(page):
                raise AnswerError("检测到平台验证，请在浏览器手动处理")
            if not await next_button.is_visible():
                can_stash = await stash_button.is_visible()
                if result or (can_stash and not needs_manual):
                    await save_button.click(timeout=2500)
                    await page.get_by_text("保存成功！", exact=True).wait_for(timeout=10000)
                completion = page.locator(".percentage_tit:visible").get_by_text("100%", exact=True)
                if can_stash and await completion.is_visible():
                    await stash_button.click(timeout=2500)
                    dialog = page.locator(".el-message-box:visible").filter(
                        has=page.get_by_text("你确定要暂存作业吗", exact=True)
                    )
                    await dialog.wait_for(timeout=10000)
                    if page.url != url or await has_visible_verification(page):
                        raise AnswerError("检测到页面变化或平台验证，已暂停暂存")
                    await dialog.get_by_role("button", name="确定", exact=True).click(timeout=2500)
                return filled, skipped
            await next_button.click(timeout=2500)
            await page.locator(f"{selector}:visible").wait_for(state="hidden", timeout=10000)
        raise AnswerError("作业考试页面已变化")
    finally:
        if not page.is_closed():
            await cdp.detach()


async def _open_next_homework(page: Page, attempted: set[tuple[str, tuple[str, ...], int]]) -> Page | None:
    url = page.url
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https" or parsed.netloc != "onlineexamh5new.zhihuishu.com"
        or parsed.path != "/stuExamWeb.html" or parsed.fragment.split("?", 1)[0] != "/webExamList"
    ):
        return None

    unsubmitted = page.locator("#examStateTabWsj.cur:visible")
    dialogs = page.locator(".el-message-box__wrapper:visible, .el-dialog__wrapper:visible")
    if not await unsubmitted.is_visible() or await dialogs.count() or await has_visible_verification(page):
        return None

    cards = page.locator(".examItemWrap:visible").filter(has=page.locator('.percentage_number:text-is("作业")'))
    occurrences = Counter()
    for card in await cards.all():
        details = await card.locator(".examTit .name, .examInfoList").all_text_contents()
        identity = tuple(" ".join(text.split()) for text in details)
        if not identity or not identity[0]:
            continue
        occurrences[identity] += 1
        key = (url, identity, occurrences[identity])
        if key in attempted:
            continue
        button = card.locator('a[title="开始答题"] .themeBg:visible')
        if not await button.is_visible():
            continue
        if page.url != url or not await unsubmitted.is_visible():
            return None
        attempted.add(key)
        paper = None
        try:
            async with page.expect_popup(timeout=5000) as result:
                await button.click(timeout=2500)
            paper = await result.value
            await paper.wait_for_url(is_exam_paper_url, wait_until="commit", timeout=PAPER_LOAD_TIMEOUT_MS)
        except PlaywrightError as exc:
            if paper is None:
                logger.warn(f"作业「{identity[0]}」未打开答题窗口，请在浏览器检查作业列表。", shift=True)
            elif not paper.is_closed():
                logger.warn(f"作业「{identity[0]}」未能及时进入答题页，关闭当前窗口后才会打开下一份。", shift=True)
            logger.debug(logger.summarize_exception(exc))
        return paper
    return None


async def watch_exam_pages(entry_page: Page, api_key: str) -> None:
    pages = set()
    handled = {}
    reloaded = {}
    attempted = set()
    active_homework = None

    def track(page: Page) -> None:
        pages.add(page)
        page.on("popup", track)

    track(entry_page)
    while pages:
        for page in tuple(pages):
            if page.is_closed():
                pages.discard(page)
                handled.pop(page, None)
                reloaded.pop(page, None)
                continue
            url = page.url
            if not is_exam_paper_url(url):
                handled.pop(page, None)
                reloaded.pop(page, None)
                continue
            if handled.get(page) == url:
                continue
            try:
                if await has_visible_verification(page):
                    continue
                question = page.locator(f"{QUESTION}:visible").first
                if reloaded.get(page) == url:
                    if not await question.is_visible():
                        continue
                else:
                    try:
                        await question.wait_for(timeout=PAPER_LOAD_TIMEOUT_MS)
                    except PlaywrightTimeoutError:
                        if await has_visible_verification(page) or page.url != url:
                            continue
                        if not await question.is_visible():
                            reloaded[page] = url
                            logger.info("等待首题加载超时，正在刷新当前试卷。", shift=True)
                            await page.reload(wait_until="commit", timeout=PAPER_LOAD_TIMEOUT_MS)
                            if page.url != url:
                                continue
                            await question.wait_for(timeout=PAPER_LOAD_TIMEOUT_MS)
                if await has_visible_verification(page) or page.url != url:
                    continue
                handled[page] = url
                filled, skipped = await fill_exam(page, api_key)
                logger.info(f"本卷自动作答 {filled} 题，待手动处理 {skipped} 题，请检查后自行交卷。", shift=True)
            except AnswerError as exc:
                logger.warn(f"{exc}，请在浏览器手动处理当前试卷。", shift=True)
            except PlaywrightError as exc:
                if not page.is_closed():
                    logger.warn("题目加载或保存失败，请在浏览器检查当前试卷。", shift=True)
                    logger.debug(logger.summarize_exception(exc))
        if (active_homework is None or active_homework.is_closed()) and not any(
            not page.is_closed() and is_exam_paper_url(page.url) for page in pages
        ):
            for page in tuple(pages):
                if page.is_closed():
                    continue
                try:
                    active_homework = await _open_next_homework(page, attempted)
                    if active_homework is not None:
                        break
                except PlaywrightError as exc:
                    if not page.is_closed():
                        logger.debug_throttled("homework-list", logger.summarize_exception(exc))
        if pages:
            await asyncio.sleep(0.5)
