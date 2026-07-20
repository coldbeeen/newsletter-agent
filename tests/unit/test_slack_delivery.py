from unittest.mock import patch

import httpx
import pytest
import respx

from newsletter_agent.delivery.slack import SlackDeliveryFailed, send_to_slack


@pytest.fixture(autouse=True)
def _no_real_sleep():
    with patch("time.sleep", return_value=None):
        yield


@respx.mock
def test_three_consecutive_500s_raises_slack_delivery_failed():
    route = respx.post("https://hooks.slack.com/services/test").mock(
        return_value=httpx.Response(500)
    )

    with pytest.raises(SlackDeliveryFailed):
        send_to_slack("https://hooks.slack.com/services/test", "리포트 내용")

    assert route.call_count == 3


@respx.mock
def test_successful_post_does_not_raise():
    respx.post("https://hooks.slack.com/services/test").mock(return_value=httpx.Response(200))

    send_to_slack("https://hooks.slack.com/services/test", "리포트 내용")
