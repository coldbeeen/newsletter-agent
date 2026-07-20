from bs4 import BeautifulSoup

# 발신자별 본문영역 규칙: footer 시작 지점을 나타내는 마커(텍스트 일부, 대소문자 무시).
# 마커가 발견되면 그 지점부터의 태그를 모두 제거한다. 발신자 규칙이 없으면 전체 본문을 사용.
SENDER_FOOTER_MARKERS: dict[str, tuple[str, ...]] = {
    "dan@tldrnewsletter.com": ("unsubscribe", "advertise with tldr", "manage your subscriptions"),
    "news@hada.io": ("수신거부", "unsubscribe"),
    "newsletter@mail.routinecrew.net": ("구독 해지", "unsubscribe"),
}


def _trim_footer(soup: BeautifulSoup, markers: tuple[str, ...]) -> None:
    if not markers:
        return
    root = soup.body or soup
    for element in soup.find_all(string=True):
        text_lower = element.strip().lower()
        if not text_lower:
            continue
        if not any(marker.lower() in text_lower for marker in markers):
            continue

        # 마커를 포함한 최상위(root의 직계 자식) 태그를 찾아, 그 지점부터 이후 형제를 모두 제거한다.
        marker_ancestor = element
        while marker_ancestor.parent is not None and marker_ancestor.parent is not root:
            marker_ancestor = marker_ancestor.parent
        if marker_ancestor is root:
            continue

        for sibling in list(marker_ancestor.find_next_siblings()):
            sibling.decompose()
        marker_ancestor.decompose()
        return


def extract_body_region(html: str, sender_address: str | None = None) -> BeautifulSoup:
    """발신자별 footer 컷오프를 적용한 본문 영역을 BeautifulSoup 객체로 반환한다."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "head", "title"]):
        tag.decompose()

    markers = SENDER_FOOTER_MARKERS.get((sender_address or "").strip().lower(), ())
    _trim_footer(soup, markers)
    return soup


def extract_visible_text(html: str, sender_address: str | None = None) -> str:
    soup = extract_body_region(html, sender_address)
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
