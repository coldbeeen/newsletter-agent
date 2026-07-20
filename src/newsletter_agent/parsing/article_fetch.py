from dataclasses import dataclass
from typing import Literal

import httpx
from bs4 import BeautifulSoup

from newsletter_agent.logging_config import get_logger

logger = get_logger(__name__)

FetchStatus = Literal["ok", "not_found", "blocked"]

# 403 응답이더라도 Cloudflare 등 봇 차단으로 보이는지 판별하기 위한 본문 마커.
_BLOCKED_BODY_MARKERS = (
    "cloudflare",
    "access denied",
    "checking your browser",
    "captcha",
)
_LOGIN_REQUIRED_MARKERS = ("please log in", "로그인이 필요", "sign in to continue")


@dataclass(frozen=True)
class FetchResult:
    status: FetchStatus
    text: str | None
    reason: str


def fetch_article(url: str, http_client: httpx.Client) -> FetchResult:
    try:
        response = http_client.get(url, follow_redirects=True, timeout=15.0)
    except httpx.TimeoutException:
        logger.info("Fetch timed out for %s", url)
        return FetchResult(status="not_found", text=None, reason="timeout")
    except httpx.HTTPError as exc:
        logger.info("Fetch failed for %s: %s", url, exc)
        return FetchResult(status="not_found", text=None, reason=type(exc).__name__)

    if response.status_code == 403:
        logger.info("Fetch blocked (403) for %s", url)
        return FetchResult(status="blocked", text=None, reason="403")
    if response.status_code == 404:
        logger.info("Fetch not found (404) for %s", url)
        return FetchResult(status="not_found", text=None, reason="404")
    if response.status_code >= 400:
        logger.info("Fetch failed (%s) for %s", response.status_code, url)
        return FetchResult(
            status="not_found", text=None, reason=str(response.status_code)
        )

    body_lower = response.text.lower()
    if any(marker in body_lower for marker in _BLOCKED_BODY_MARKERS):
        logger.info("Fetch blocked (bot-detection marker) for %s", url)
        return FetchResult(status="blocked", text=None, reason="bot_detection_marker")
    if any(marker in body_lower for marker in _LOGIN_REQUIRED_MARKERS):
        logger.info("Fetch not accessible (login required) for %s", url)
        return FetchResult(status="not_found", text=None, reason="login_required")

    text = _extract_main_text(response.text)
    if not text:
        logger.info("Fetch succeeded but no extractable text for %s", url)
        return FetchResult(status="not_found", text=None, reason="empty_content")
    return FetchResult(status="ok", text=text, reason="ok")


def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "nav", "footer"]):
        tag.decompose()

    container = soup.find("article") or soup.find("main")
    if container is None:
        # 문단 밀도 휴리스틱: 텍스트가 가장 많은 <p> 묶음을 가진 컨테이너를 선택.
        candidates = soup.find_all(["div", "section"])
        container = max(
            candidates,
            key=lambda c: sum(len(p.get_text()) for p in c.find_all("p", recursive=False)),
            default=soup,
        )

    paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)
    return text.strip()
