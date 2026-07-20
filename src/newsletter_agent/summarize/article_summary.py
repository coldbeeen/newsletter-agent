import json
import re

from newsletter_agent.logging_config import get_logger
from newsletter_agent.models import ArticleSummary
from newsletter_agent.parsing.article_fetch import FetchResult
from newsletter_agent.summarize.client import ClaudeCallFailed, ClaudeClient

FETCH_STATUS_LABELS = {
    "not_found": "원문 확인 불가",
    "blocked": "접근 차단됨",
}

SUMMARY_FAILED_PLACEHOLDER = "요약 실패"

_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

logger = get_logger(__name__)


def summarize_article(
    claude_client: ClaudeClient,
    fetch_result: FetchResult,
    excerpt: str,
    anchor_text: str,
) -> ArticleSummary:
    """기사를 요약하고 주제 태그를 함께 생성한다.

    fetch 성공 시 본문 전체를, 실패 시 뉴스레터 발췌문(excerpt)만으로 요약한다.
    Claude 호출이 재시도 끝에 최종 실패하면 해당 기사만 플레이스홀더로 대체하고
    전체 파이프라인은 계속 진행한다(부분 리포트).
    """
    source_text = fetch_result.text if fetch_result.status == "ok" else excerpt
    source_text = source_text or anchor_text or "(본문 없음)"

    prompt = (
        "다음 기사 내용을 한국어로 3~5문장으로 요약하고, "
        "가장 적절한 주제 태그 하나를 골라줘 (예: AI, 개발, 스타트업, 마케팅, 데이터, 기타). "
        '반드시 JSON 형식 {"summary": "...", "topic": "..."} 로만 응답해.\n\n'
        f"{source_text}"
    )
    try:
        raw = claude_client.summarize_text(prompt, sentence_range=(3, 5))
    except ClaudeCallFailed:
        logger.error("Article summarization failed permanently; using placeholder")
        return ArticleSummary(text=SUMMARY_FAILED_PLACEHOLDER, topic="기타")

    summary_text, topic = _parse_summary_response(raw)

    if fetch_result.status in FETCH_STATUS_LABELS:
        label = FETCH_STATUS_LABELS[fetch_result.status]
        summary_text = f"[{label}] {summary_text}"

    return ArticleSummary(text=summary_text, topic=topic)


def _parse_summary_response(raw: str) -> tuple[str, str]:
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        try:
            data = json.loads(match.group(0))
            return data.get("summary", raw).strip(), data.get("topic", "기타").strip()
        except json.JSONDecodeError:
            pass
    return raw.strip(), "기타"
