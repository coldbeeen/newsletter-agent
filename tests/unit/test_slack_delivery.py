from unittest.mock import patch

import httpx
import pytest
import respx

from newsletter_agent.delivery.slack import SlackDeliveryFailed, send_to_slack


@pytest.fixture(autouse=True)
def _no_real_sleep():
    with patch("time.sleep", return_value=None):
        yield


_SAMPLE_BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "리포트 내용"}}]


@respx.mock
def test_three_consecutive_500s_raises_slack_delivery_failed():
    route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(SlackDeliveryFailed):
        send_to_slack("https://hooks.slack.com/services/test", _SAMPLE_BLOCKS, "리포트 내용")

    assert route.call_count == 3


@respx.mock
def test_successful_post_does_not_raise():
    respx.post("https://hooks.slack.com/services/test").mock(return_value=httpx.Response(200))

    send_to_slack("https://hooks.slack.com/services/test", _SAMPLE_BLOCKS, "리포트 내용")


@respx.mock
def test_payload_sends_blocks_and_fallback_text():
    route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(200)
    )

    send_to_slack("https://hooks.slack.com/services/test", _SAMPLE_BLOCKS, "폴백 텍스트")

    import json

    sent_body = json.loads(route.calls.last.request.content)
    assert sent_body["blocks"] == _SAMPLE_BLOCKS
    assert sent_body["text"] == "폴백 텍스트"


@respx.mock
def test_more_than_50_blocks_sent_as_multiple_requests():
    route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(200)
    )
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": str(i)}} for i in range(120)]

    send_to_slack("https://hooks.slack.com/services/test", blocks, "폴백 텍스트")

    assert route.call_count == 3


@respx.mock
def test_more_than_50_blocks_each_request_within_limit():
    import json

    route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(200)
    )
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": str(i)}} for i in range(120)]

    send_to_slack("https://hooks.slack.com/services/test", blocks, "폴백 텍스트")

    sent_blocks_per_call = [
        json.loads(call.request.content)["blocks"] for call in route.calls
    ]
    assert [len(b) for b in sent_blocks_per_call] == [50, 50, 20]
    assert [block for chunk in sent_blocks_per_call for block in chunk] == blocks
