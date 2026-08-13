from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

# 구독해지/SNS 공유/추적 픽셀 등, 기사 링크로 취급하지 않을 URL 키워드 (호스트/경로/쿼리 어디든 매칭).
COMMON_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "unsubscribe",
    "twitter.com",
    "x.com/intent",
    "facebook.com/share",
    "linkedin.com/share",
    "mailto:",
    "share?url=",
    "tracking-pixel",
    "/pixel.",
)

# 정규화 시 제거할 추적용 쿼리 파라미터 접두어/이름.
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = {"ref", "ref_src", "source", "fbclid", "gclid"}

_MAX_REDIRECT_HOPS = 5


@dataclass(frozen=True)
class RawLink:
    url: str
    anchor_text: str
    order: int


def extract_candidate_links(body_region: BeautifulSoup) -> list[RawLink]:
    links: list[RawLink] = []
    for index, anchor in enumerate(body_region.find_all("a", href=True)):
        url = anchor["href"].strip()
        if not url or url.startswith("#"):
            continue
        if is_excluded_by_common_filters(url):
            continue
        anchor_text = anchor.get_text(strip=True)
        links.append(RawLink(url=url, anchor_text=anchor_text, order=index))
    return links


def is_excluded_by_common_filters(url: str) -> bool:
    lowered = url.lower()
    return any(keyword in lowered for keyword in COMMON_EXCLUDE_KEYWORDS)


def resolve_redirect(url: str, http_client: httpx.Client) -> str:
    """추적용 리다이렉트 URL을 최종 목적지 URL로 해석한다."""
    current = url
    for _ in range(_MAX_REDIRECT_HOPS):
        try:
            response = http_client.head(current, follow_redirects=False)
        except httpx.HTTPError:
            return current
        if response.is_redirect and "location" in response.headers:
            next_url = httpx.URL(current).join(response.headers["location"])
            current = str(next_url)
            continue
        return current
    return current


def normalize_url(url: str) -> str:
    """중복 제거용 정규화: 추적 쿼리 파라미터 제거, fragment 제거, 끝 슬래시 통일."""
    parsed = urlparse(url)
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith(_TRACKING_PARAM_PREFIXES)
        and key.lower() not in _TRACKING_PARAM_NAMES
    ]
    path = parsed.path.rstrip("/") or "/"
    normalized = parsed._replace(
        path=path,
        query=urlencode(kept_params),
        fragment="",
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
    )
    return urlunparse(normalized)


def select_top_links(links: list[RawLink], cap: int = 50) -> tuple[list[RawLink], bool]:
    """등장 순서 기준 상위 cap개까지만 선택. 두 번째 값은 상한 적용 여부."""
    ordered = sorted(links, key=lambda link: link.order)
    if len(ordered) <= cap:
        return ordered, False
    return ordered[:cap], True
