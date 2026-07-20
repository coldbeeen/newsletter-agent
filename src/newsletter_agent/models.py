from dataclasses import dataclass, field
from datetime import datetime

from newsletter_agent.parsing.article_fetch import FetchResult


@dataclass
class EmailMessage:
    msg_id: str
    from_addr: str
    from_display_name: str
    subject: str
    received_at: datetime
    html_body: str


@dataclass(frozen=True)
class NewsletterId:
    name: str
    matched: bool = True


@dataclass
class Newsletter:
    newsletter_id: NewsletterId
    email: EmailMessage


@dataclass
class ArticleSummary:
    text: str
    topic: str


@dataclass
class Article:
    url: str
    normalized_url: str
    title: str
    excerpt: str
    fetch_result: FetchResult
    summary: ArticleSummary
    source_newsletters: list[NewsletterId] = field(default_factory=list)
