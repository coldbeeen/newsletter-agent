from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from newsletter_agent.logging_config import get_logger

logger = get_logger(__name__)


class ClaudeCallFailed(Exception):
    """Claude API 호출이 재시도(최대 3회) 끝에 최종적으로 실패했을 때 발생."""


class ClaudeClient:
    def __init__(self, api_key: str, model: str):
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def summarize_text(self, text: str, sentence_range: tuple[int, int] = (3, 5)) -> str:
        low, high = sentence_range
        prompt = (
            f"다음 뉴스레터 본문을 한국어로 {low}~{high}문장으로 요약해줘. "
            "핵심 내용만 간결하게 정리하고, 문장 외의 다른 설명은 붙이지 마.\n\n"
            f"{text}"
        )
        try:
            return self._call(prompt)
        except Exception as exc:
            logger.warning("Claude call failed after retries: %s", exc)
            raise ClaudeCallFailed(str(exc)) from exc

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def _call(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
