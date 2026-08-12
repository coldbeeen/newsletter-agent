from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from newsletter_agent.logging_config import get_logger

logger = get_logger(__name__)

FetchStatus = Literal["ok", "not_found", "blocked"]

# 200 응답이더라도 봇 차단 인터스티셜로 보이는지 판별하기 위한 본문 마커.
# "cloudflare"나 "captcha" 단독으로는 그 주제를 다루는 정상 기사와 구별할 수 없으므로,
# 실제 차단 페이지에서 쓰이는 더 구체적인 문구만 사용한다.
_BLOCKED_BODY_MARKERS = (
    "access denied",
    "checking your browser",
    "verify you are human",
    "enable javascript and cookies to continue",
    "ray id",
)
_LOGIN_REQUIRED_MARKERS = ("please log in", "로그인이 필요", "sign in to continue")

# GeekNews(hada.io) 뉴스레터의 기사 링크는 원문이 아니라 hada.io 자체 토픽(코멘트) 페이지를
# 가리킨다. 실제 원문 링크는 이 클래스를 가진 앵커 태그에 들어있다.
_HADA_IO_HOST_SUFFIX = "hada.io"
_HADA_IO_ORIGINAL_LINK_CLASS = "topic-title-link"


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

    original_url = _find_hada_io_original_link(url, response.text)
    if original_url is not None:
        logger.info("Following hada.io topic page %s to original article %s", url, original_url)
        return fetch_article(original_url, http_client)

    text = _extract_main_text(response.text)
    if not text:
        logger.info("Fetch succeeded but no extractable text for %s", url)
        return FetchResult(status="not_found", text=None, reason="empty_content")
    return FetchResult(status="ok", text=text, reason="ok")


def _find_hada_io_original_link(url: str, html: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if not (host == _HADA_IO_HOST_SUFFIX or host.endswith(f".{_HADA_IO_HOST_SUFFIX}")):
        return None

    soup = BeautifulSoup(html, "lxml")
    anchor = soup.find("a", class_=_HADA_IO_ORIGINAL_LINK_CLASS, href=True)
    if anchor is None:
        return None
    return anchor["href"].strip()


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
