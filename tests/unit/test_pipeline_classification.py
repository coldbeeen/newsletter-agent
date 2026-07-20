from datetime import datetime
from pathlib import Path

from newsletter_agent.mail.whitelist import Whitelist
from newsletter_agent.models import EmailMessage
from newsletter_agent.pipeline import _classify_all

WHITELIST_PATH = Path(__file__).parent.parent.parent / "whitelist.yaml"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "emails"


def _make_email(from_addr: str, display_name: str, subject: str, fixture_name: str) -> EmailMessage:
    html = FIXTURES.joinpath(fixture_name).read_text(encoding="utf-8")
    return EmailMessage(
        msg_id=f"{from_addr}-{display_name}",
        from_addr=from_addr,
        from_display_name=display_name,
        subject=subject,
        received_at=datetime(2026, 7, 19, 12, 0, 0),
        html_body=html,
    )


def test_multiple_tldr_variants_classified_distinctly_without_crashing():
    whitelist = Whitelist.load(WHITELIST_PATH)
    emails = [
        _make_email("dan@tldrnewsletter.com", "TLDR AI", "AI Digest", "tldr_ai_body.html"),
        _make_email("dan@tldrnewsletter.com", "TLDR IT", "IT Digest", "tldr_it_body.html"),
        _make_email(
            "dan@tldrnewsletter.com",
            "TLDR Something Weird",
            "Mystery Digest",
            "tldr_unknown_body.html",
        ),
    ]

    newsletters = _classify_all(whitelist, emails)

    by_subject = {nl.email.subject: nl.newsletter_id.name for nl in newsletters}
    assert by_subject["AI Digest"] == "TLDR AI"
    assert by_subject["IT Digest"] == "TLDR IT"
    assert by_subject["Mystery Digest"] == "TLDR(미분류)"
