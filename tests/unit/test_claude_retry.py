from unittest.mock import MagicMock, patch

import pytest

from newsletter_agent.summarize.client import ClaudeCallFailed, ClaudeClient


@pytest.fixture(autouse=True)
def _no_real_sleep():
    with patch("time.sleep", return_value=None):
        yield


def _fake_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


@patch("newsletter_agent.summarize.client.Anthropic")
def test_transient_errors_then_success_records_success_on_third_attempt(mock_anthropic_cls):
    mock_client = mock_anthropic_cls.return_value
    mock_client.messages.create.side_effect = [
        RuntimeError("transient 1"),
        RuntimeError("transient 2"),
        _fake_response("성공 응답"),
    ]

    client = ClaudeClient(api_key="test-key", model="claude-haiku-4-5")
    result = client.summarize_text("본문")

    assert result == "성공 응답"
    assert mock_client.messages.create.call_count == 3


@patch("newsletter_agent.summarize.client.Anthropic")
def test_three_consecutive_failures_raises_claude_call_failed(mock_anthropic_cls):
    mock_client = mock_anthropic_cls.return_value
    mock_client.messages.create.side_effect = RuntimeError("permanent failure")

    client = ClaudeClient(api_key="test-key", model="claude-haiku-4-5")

    with pytest.raises(ClaudeCallFailed):
        client.summarize_text("본문")

    assert mock_client.messages.create.call_count == 3
