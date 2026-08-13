from newsletter_agent.models import Article, ArticleSummary, NewsletterId
from newsletter_agent.parsing.article_fetch import FetchResult
from newsletter_agent.summarize.report_synthesis import chunk_blocks, compose_slack_blocks


def _article(title, url, topic, summary_text, source_name):
    return Article(
        url=url,
        normalized_url=url,
        title=title,
        excerpt="",
        fetch_result=FetchResult(status="ok", text="x", reason="ok"),
        summary=ArticleSummary(text=summary_text, topic=topic),
        source_newsletters=[NewsletterId(name=source_name)],
    )


def test_compose_slack_blocks_uses_mrkdwn_links_not_markdown_syntax():
    """Slack Block Kit의 mrkdwn은 <url|텍스트> 문법을 쓴다. 표준 마크다운 [텍스트](url)이
    섞여 들어가면 Slack에서 그대로 텍스트로 노출되므로 절대 포함되면 안 된다."""
    grouped = {
        "AI": [_article("OpenAI 발표", "https://example.com/a1", "AI", "요약 내용.", "TLDR AI")],
    }

    blocks = compose_slack_blocks("전체 요약입니다.", grouped, [], [])

    serialized = str(blocks)
    assert "[OpenAI 발표](https://example.com/a1)" not in serialized
    assert "<https://example.com/a1|OpenAI 발표>" in serialized
    assert "##" not in serialized


def test_compose_slack_blocks_includes_topic_and_article_count():
    grouped = {
        "AI": [
            _article("기사1", "https://example.com/1", "AI", "요약1", "TLDR AI"),
            _article("기사2", "https://example.com/2", "AI", "요약2", "TLDR AI"),
        ],
    }

    blocks = compose_slack_blocks("요약", grouped, [], [])

    serialized = str(blocks)
    assert "AI" in serialized
    assert "2건" in serialized


def test_compose_slack_blocks_no_new_articles_shows_message():
    from newsletter_agent.summarize.report_synthesis import NO_NEW_ARTICLES_MESSAGE

    blocks = compose_slack_blocks("오늘 새로 전달할 기사가 없습니다.", {}, [], [])

    serialized = str(blocks)
    assert NO_NEW_ARTICLES_MESSAGE in serialized


def test_compose_slack_blocks_includes_cap_and_unclassified_notices():
    grouped = {"AI": [_article("기사1", "https://example.com/1", "AI", "요약1", "TLDR AI")]}

    blocks = compose_slack_blocks(
        "요약",
        grouped,
        ["링크가 많아 상위 50개까지만 처리한 뉴스레터: TLDR AI"],
        ["표시이름 미분류로 처리된 뉴스레터: TLDR(미분류)"],
    )

    serialized = str(blocks)
    assert "상위 50개까지만 처리한 뉴스레터: TLDR AI" in serialized
    assert "표시이름 미분류로 처리된 뉴스레터: TLDR(미분류)" in serialized


def test_chunk_blocks_splits_into_groups_of_max_size():
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": str(i)}} for i in range(120)]

    chunks = chunk_blocks(blocks, max_size=50)

    assert len(chunks) == 3
    assert [len(c) for c in chunks] == [50, 50, 20]


def test_chunk_blocks_preserves_order_and_content():
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": str(i)}} for i in range(120)]

    chunks = chunk_blocks(blocks, max_size=50)

    flattened = [block for chunk in chunks for block in chunk]
    assert flattened == blocks


def test_chunk_blocks_under_limit_returns_single_chunk():
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": str(i)}} for i in range(10)]

    chunks = chunk_blocks(blocks, max_size=50)

    assert len(chunks) == 1
    assert chunks[0] == blocks
