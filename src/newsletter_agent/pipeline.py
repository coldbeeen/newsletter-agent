import sys
import time
from datetime import date
from pathlib import Path

import httpx

from newsletter_agent.config import Settings
from newsletter_agent.dedup.same_day import merge_same_day
from newsletter_agent.dedup.seen_store import SeenStore
from newsletter_agent.delivery.console import print_report
from newsletter_agent.delivery.slack import SlackDeliveryFailed, send_to_slack
from newsletter_agent.logging_config import get_logger
from newsletter_agent.mail.client import ImapAuthenticationFailed, MailClient
from newsletter_agent.mail.time_window import kst_today_window
from newsletter_agent.mail.whitelist import Whitelist
from newsletter_agent.models import Article, Newsletter
from newsletter_agent.parsing.article_fetch import fetch_article
from newsletter_agent.parsing.html_body import extract_body_region
from newsletter_agent.parsing.links import (
    extract_candidate_links,
    normalize_url,
    resolve_redirect,
    select_top_links,
)
from newsletter_agent.summarize.article_summary import summarize_article
from newsletter_agent.summarize.client import ClaudeClient
from newsletter_agent.summarize.report_synthesis import (
    NO_NEWSLETTERS_MESSAGE,
    compose_markdown_report,
    group_by_topic,
    synthesize_overall_summary,
)

WHITELIST_PATH = Path.cwd() / "whitelist.yaml"
SEEN_URLS_PATH = Path.cwd() / "state" / "seen_urls.json"
LINK_CAP = 50

logger = get_logger(__name__)


def _classify_all(whitelist: Whitelist, emails) -> list[Newsletter]:
    newsletters = []
    for email in emails:
        newsletter_id = whitelist.classify(email.from_addr, email.from_display_name)
        newsletters.append(Newsletter(newsletter_id=newsletter_id, email=email))
    return newsletters


def _process_newsletter_articles(
    newsletter: Newsletter, claude_client: ClaudeClient, http_client: httpx.Client
) -> tuple[list[Article], bool]:
    """뉴스레터 1건에서 기사 링크를 추출/fetch/요약한다. 두 번째 값은 링크 상한 적용 여부."""
    body_region = extract_body_region(
        newsletter.email.html_body, newsletter.email.from_addr
    )
    raw_links = extract_candidate_links(body_region)
    top_links, cap_applied = select_top_links(raw_links, cap=LINK_CAP)
    if cap_applied:
        logger.info(
            "Link cap applied for %s (subject=%r): %d links found, capped at %d",
            newsletter.newsletter_id.name,
            newsletter.email.subject,
            len(raw_links),
            LINK_CAP,
        )

    articles: list[Article] = []
    for link in top_links:
        resolved_url = resolve_redirect(link.url, http_client)
        fetch_result = fetch_article(resolved_url, http_client)
        excerpt = link.anchor_text
        summary = summarize_article(claude_client, fetch_result, excerpt, link.anchor_text)
        articles.append(
            Article(
                url=resolved_url,
                normalized_url=normalize_url(resolved_url),
                title=link.anchor_text or resolved_url,
                excerpt=excerpt,
                fetch_result=fetch_result,
                summary=summary,
                source_newsletters=[newsletter.newsletter_id],
            )
        )
    return articles, cap_applied


def _collect_all_articles(
    newsletters: list[Newsletter], claude_client: ClaudeClient, http_client: httpx.Client
) -> tuple[list[Article], dict[str, bool]]:
    """모든 뉴스레터의 기사를 수집한다. 두 번째 값은 뉴스레터명 -> 캡 적용 여부."""
    all_articles: list[Article] = []
    cap_applied_by_newsletter: dict[str, bool] = {}
    for newsletter in newsletters:
        articles, cap_applied = _process_newsletter_articles(
            newsletter, claude_client, http_client
        )
        all_articles.extend(articles)
        cap_applied_by_newsletter[newsletter.newsletter_id.name] = cap_applied
    return all_articles, cap_applied_by_newsletter


def _compose_final_report(
    articles: list[Article],
    claude_client: ClaudeClient,
    cap_applied_by_newsletter: dict[str, bool],
    unclassified_names: list[str],
) -> str:
    cap_notices = [
        f"링크가 많아 상위 {LINK_CAP}개까지만 처리한 뉴스레터: {name}"
        for name, applied in cap_applied_by_newsletter.items()
        if applied
    ]
    unclassified_notices = (
        [f"표시이름 미분류로 처리된 뉴스레터: {', '.join(unclassified_names)}"]
        if unclassified_names
        else []
    )

    grouped = group_by_topic(articles)
    overall_summary = (
        synthesize_overall_summary(claude_client, grouped)
        if grouped
        else "오늘 새로 전달할 기사가 없습니다."
    )
    return compose_markdown_report(overall_summary, grouped, cap_notices, unclassified_notices)


def _deliver(report: str, settings: Settings, delivery: str) -> None:
    if delivery == "console":
        print_report(report)
        return

    if not settings.slack_webhook_url:
        logger.error("SLACK_WEBHOOK_URL not configured; falling back to console output")
        print_report(report)
        return

    try:
        send_to_slack(settings.slack_webhook_url, report)
    except SlackDeliveryFailed:
        logger.error("Slack delivery failed permanently; exiting with failure status")
        sys.exit(1)


def _send_error_alert(settings: Settings, message: str) -> None:
    if settings.slack_webhook_url:
        try:
            send_to_slack(settings.slack_webhook_url, f"에러 발생: {message}")
        except SlackDeliveryFailed:
            logger.error("Failed to deliver error alert to Slack")
    logger.error(message)


def run(delivery: str = "slack") -> None:
    start_time = time.monotonic()
    settings = Settings.from_env()
    whitelist = Whitelist.load(WHITELIST_PATH)

    mail_client = MailClient(
        host=settings.naver_imap_host,
        port=settings.naver_imap_port,
        user=settings.naver_imap_user,
        password=settings.naver_imap_app_password,
    )
    claude_client = ClaudeClient(
        api_key=settings.anthropic_api_key, model=settings.claude_model
    )

    since_date_kst = kst_today_window()
    try:
        emails = mail_client.fetch_recent(whitelist.addresses(), since_date_kst)
    except ImapAuthenticationFailed as exc:
        _send_error_alert(settings, f"IMAP 인증 실패: {exc}")
        sys.exit(1)

    newsletters = _classify_all(whitelist, emails)
    unclassified_names = []
    for newsletter in newsletters:
        if not newsletter.newsletter_id.matched:
            logger.warning(
                "Unclassified newsletter fell back to %r (subject=%r)",
                newsletter.newsletter_id.name,
                newsletter.email.subject,
            )
            unclassified_names.append(newsletter.newsletter_id.name)

    if not newsletters:
        _deliver(NO_NEWSLETTERS_MESSAGE, settings, delivery)
        logger.info("Pipeline finished in %.1fs (no newsletters)", time.monotonic() - start_time)
        return

    seen_store = SeenStore.load(SEEN_URLS_PATH)

    with httpx.Client() as http_client:
        all_articles, cap_applied_by_newsletter = _collect_all_articles(
            newsletters, claude_client, http_client
        )

    merged_articles = merge_same_day(all_articles)
    new_articles = seen_store.filter_new(merged_articles)

    report = _compose_final_report(
        new_articles, claude_client, cap_applied_by_newsletter, unclassified_names
    )
    _deliver(report, settings, delivery)

    today = date.today()
    seen_store.record(new_articles, today)
    seen_store.prune(settings.seen_urls_retention_days, today)
    seen_store.save(SEEN_URLS_PATH)

    logger.info("Pipeline finished in %.1fs (%d articles delivered)", time.monotonic() - start_time, len(new_articles))


def main() -> None:
    delivery = "console" if "--console" in sys.argv[1:] else "slack"
    run(delivery=delivery)


if __name__ == "__main__":
    main()
