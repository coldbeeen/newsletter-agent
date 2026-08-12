import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from newsletter_agent.logging_config import get_logger

logger = get_logger(__name__)


class SlackDeliveryFailed(Exception):
    """Slack Webhook 전송이 재시도(최대 3회) 끝에 최종적으로 실패했을 때 발생."""


def send_to_slack(webhook_url: str, blocks: list[dict], fallback_text: str) -> None:
    """Slack Incoming Webhook으로 Block Kit blocks를 전송한다.
    fallback_text는 알림 미리보기/접근성용 텍스트로 blocks와 함께 전송된다."""
    try:
        _post_with_retry(webhook_url, blocks, fallback_text)
    except Exception as exc:
        logger.error("Slack delivery failed after retries: %s", exc)
        raise SlackDeliveryFailed(str(exc)) from exc


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _post_with_retry(webhook_url: str, blocks: list[dict], fallback_text: str) -> None:
    with httpx.Client() as client:
        response = client.post(
            webhook_url, json={"blocks": blocks, "text": fallback_text}, timeout=15.0
        )
        response.raise_for_status()
