import unittest

from modules.answering import AnswerError, _AnswerClient, ask_codex, parse_answer
from acp.schema import AgentMessageChunk, AgentThoughtChunk, TextContentBlock


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
    async def test_stream_uses_answer_chunks_and_excludes_reasoning(self):
        client = _AnswerClient()
        await client.session_update("test", AgentThoughtChunk(
            session_update="agent_thought_chunk",
            content=TextContentBlock(type="text", text="思考内容"),
        ))
        await client.session_update("test", AgentMessageChunk(
            session_update="agent_message_chunk",
            content=TextContentBlock(type="text", text="Warning: 配置提示"),
        ))
        for text in ('{"answers":', '[2]}'):
            await client.session_update("test", AgentMessageChunk(
                session_update="agent_message_chunk",
                message_id="answer",
                content=TextContentBlock(type="text", text=text),
            ))
        self.assertEqual(parse_answer(client.text, 2), [1])
        response = await client.request_permission("test", None, [])
        self.assertEqual(response.outcome.outcome, "cancelled")

    async def test_incomplete_question_fails_before_starting_agent(self):
        for question, options in (("", ["a", "b"]), ("题目", []), ("题目", ["a", ""])):
            with self.subTest(question=question, options=options), self.assertRaises(AnswerError):
                await ask_codex(question, options)

    async def test_new_message_replaces_commentary_and_bounds_answer_length(self):
        client = _AnswerClient()
        for message_id, text in (("comment", "准备作答"), ("answer", '{"answers":[1]}')):
            await client.session_update("test", AgentMessageChunk(
                session_update="agent_message_chunk", message_id=message_id,
                content=TextContentBlock(type="text", text=text),
            ))
        self.assertEqual(parse_answer(client.text, 2), [0])
        await client.session_update("test", AgentMessageChunk(
            session_update="agent_message_chunk", message_id="answer",
            content=TextContentBlock(type="text", text="x" * 5000),
        ))
        self.assertTrue(client.overflow)
        self.assertEqual(len(client.text), 4096)
