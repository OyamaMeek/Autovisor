import os
import unittest

from modules.answering import AnswerError, ask_deepseek, parse_answer


class AnswerValidationTests(unittest.TestCase):
    def test_accepts_single_multiple_and_true_false_answers(self):
        self.assertEqual(parse_answer('{"answers": [2]}', 4), [1])
        self.assertEqual(parse_answer('{"answers": [1, 3]}', 4), [0, 2])
        self.assertEqual(parse_answer('{"answers": [2]}', 2), [1])

    def test_rejects_invalid_or_ambiguous_answers(self):
        for answer in (
            '', '选 A', '```json\n{"answers": [1]}\n```', '[]',
            '{"answers": []}', '{"answers": [0]}', '{"answers": [5]}',
            '{"answers": [1, 1]}', '{"answers": [true]}',
            '{"answers": [1.0]}', '{"answers": ["1"]}',
            '{"answers": null}', '{"answer": 1}',
        ):
            with self.subTest(answer=answer), self.assertRaises(AnswerError):
                parse_answer(answer, 4)


class AnswerClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_incomplete_question_fails_before_request(self):
        for question, options in (("", ["a", "b"]), ("题目", []), ("题目", ["a", ""])):
            with self.subTest(question=question, options=options), self.assertRaisesRegex(AnswerError, "不完整"):
                await ask_deepseek(question, options, "key-for-test")

    async def test_invalid_key_cannot_be_used_as_an_authorization_header(self):
        with self.assertRaisesRegex(AnswerError, "API Key 格式无效"):
            await ask_deepseek("题目", ["a", "b"], "key\ninvalid")

    @unittest.skipUnless(os.environ.get("AUTOVISOR_TEST_DEEPSEEK") == "1", "需要显式启用 DeepSeek 服务测试")
    async def test_live_deepseek_answers_a_text_question(self):
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        self.assertTrue(api_key, "请先设置 DEEPSEEK_API_KEY")
        self.assertEqual(await ask_deepseek("单选题：1 + 1 等于多少？", ["3", "2", "5"], api_key), [1])
