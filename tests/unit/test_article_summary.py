from newsletter_agent.parsing.article_fetch import FetchResult
from newsletter_agent.summarize.article_summary import SUMMARY_FAILED_PLACEHOLDER, summarize_article
from newsletter_agent.summarize.client import ClaudeCallFailed


class _AlwaysFailsClaudeClient:
    def summarize_text(self, text: str, sentence_range=(3, 5)) -> str:
        raise ClaudeCallFailed("permanent failure")


class _SucceedsClaudeClient:
    def summarize_text(self, text: str, sentence_range=(3, 5)) -> str:
        return '{"summary": "정상 요약입니다.", "topic": "AI"}'


def test_permanent_claude_failure_substitutes_placeholder_without_raising():
    fetch_result = FetchResult(status="ok", text="본문 내용", reason="ok")

    summary = summarize_article(_AlwaysFailsClaudeClient(), fetch_result, "발췌", "앵커")

    assert summary.text == SUMMARY_FAILED_PLACEHOLDER
    assert summary.topic == "기타"


def test_successful_claude_call_returns_parsed_summary_and_topic():
    fetch_result = FetchResult(status="ok", text="본문 내용", reason="ok")

    summary = summarize_article(_SucceedsClaudeClient(), fetch_result, "발췌", "앵커")

    assert summary.text == "정상 요약입니다."
    assert summary.topic == "AI"
