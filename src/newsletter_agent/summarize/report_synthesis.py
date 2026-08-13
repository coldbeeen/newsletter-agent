from newsletter_agent.models import Article
from newsletter_agent.summarize.article_summary import SUMMARY_FAILED_PLACEHOLDER
from newsletter_agent.summarize.client import ClaudeCallFailed, ClaudeClient

NO_NEWSLETTERS_MESSAGE = "오늘 수신된 뉴스레터 없음"
NO_NEW_ARTICLES_MESSAGE = "오늘 새로 전달할 기사가 없습니다 — 모두 중복이거나 링크가 없었습니다"
OVERALL_SUMMARY_FAILED_PLACEHOLDER = "전체 요약 생성에 실패했습니다. 아래 기사별 요약을 참고해주세요."


def group_by_topic(articles: list[Article]) -> dict[str, list[Article]]:
    """기사별로 이미 부여된 topic 태그(Phase 3 article_summary에서 생성)로 그룹핑한다."""
    grouped: dict[str, list[Article]] = {}
    for article in articles:
        grouped.setdefault(article.summary.topic, []).append(article)
    return grouped


def synthesize_overall_summary(claude_client: ClaudeClient, grouped: dict[str, list[Article]]) -> str:
    """전체 기사 요약을 컨텍스트로 3~5줄의 전체 핵심 요약을 생성한다."""
    context_lines = []
    for topic, articles in grouped.items():
        for article in articles:
            context_lines.append(f"[{topic}] {article.title}: {article.summary.text}")
    context = "\n".join(context_lines)

    prompt = (
        "다음은 오늘 수집된 기사 요약 목록이다. 이를 바탕으로 오늘의 핵심 내용을 "
        "한국어로 3~5줄로 정리해줘. 각 줄은 간결한 문장으로.\n\n"
        f"{context}"
    )
    try:
        return claude_client.summarize_text(prompt, sentence_range=(3, 5))
    except ClaudeCallFailed:
        return OVERALL_SUMMARY_FAILED_PLACEHOLDER


def compose_slack_blocks(
    overall_summary: str,
    grouped: dict[str, list[Article]],
    cap_notices: list[str],
    unclassified_notices: list[str],
) -> list[dict]:
    """Slack Block Kit blocks를 구성한다. Slack Incoming Webhook은 표준 마크다운을
    지원하지 않으므로(mrkdwn 문법: *굵게*, <url|텍스트>), 표준 마크다운 문자열을
    그대로 보내면 #, [텍스트](url) 등이 날것 텍스트로 노출된다."""
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📰 데일리 다이제스트", "emoji": True},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*📌 오늘의 핵심 요약*\n{overall_summary}"},
        },
    ]

    notices = cap_notices + unclassified_notices
    if notices:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "_" + " / ".join(notices) + "_"}],
            }
        )

    if not grouped:
        blocks.append({"type": "divider"})
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": NO_NEW_ARTICLES_MESSAGE}}
        )
        return blocks

    for topic, articles in grouped.items():
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*🏷️ {topic}* ({len(articles)}건)"},
            }
        )
        for article in articles:
            source_names = ", ".join(nl.name for nl in article.source_newsletters)
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"• <{article.url}|{article.title}>\n"
                            f"  _{source_names}_ · {article.summary.text}"
                        ),
                    },
                }
            )

    return blocks


def chunk_blocks(blocks: list[dict], max_size: int = 50) -> list[list[dict]]:
    """Slack Block Kit은 메시지당 최대 50개 block만 허용하므로, 그 이상이면
    여러 메시지로 나눠 보낼 수 있도록 max_size 단위로 순서를 보존해 분할한다."""
    return [blocks[i : i + max_size] for i in range(0, len(blocks), max_size)]


def compose_markdown_report(
    overall_summary: str,
    grouped: dict[str, list[Article]],
    cap_notices: list[str],
    unclassified_notices: list[str],
) -> str:
    sections = ["# 데일리 다이제스트\n", "## 오늘의 핵심 요약\n", f"{overall_summary}\n"]

    if cap_notices:
        sections.append("_" + " / ".join(cap_notices) + "_\n")
    if unclassified_notices:
        sections.append("_" + " / ".join(unclassified_notices) + "_\n")

    if not grouped:
        sections.append(f"{NO_NEW_ARTICLES_MESSAGE}\n")
        return "\n".join(sections)

    for topic, articles in grouped.items():
        sections.append(f"## {topic}\n")
        for article in articles:
            source_names = ", ".join(nl.name for nl in article.source_newsletters)
            sections.append(
                f"- [{article.title}]({article.url}) ({source_names}) — {article.summary.text}"
            )
        sections.append("")

    return "\n".join(sections)


__all__ = [
    "NO_NEWSLETTERS_MESSAGE",
    "NO_NEW_ARTICLES_MESSAGE",
    "OVERALL_SUMMARY_FAILED_PLACEHOLDER",
    "SUMMARY_FAILED_PLACEHOLDER",
    "chunk_blocks",
    "compose_markdown_report",
    "compose_slack_blocks",
    "group_by_topic",
    "synthesize_overall_summary",
]
