import httpx
import respx

from newsletter_agent.parsing.html_body import extract_body_region
from newsletter_agent.parsing.links import (
    extract_candidate_links,
    is_excluded_by_common_filters,
    normalize_url,
    resolve_redirect,
    select_top_links,
)
from newsletter_agent.parsing.links import RawLink


def test_extract_candidate_links_honors_sender_footer_cutoff():
    html = """
    <html><body>
    <p>기사 1: <a href="https://example.com/article1">읽기</a></p>
    <p>기사 2: <a href="https://example.com/article2">읽기</a></p>
    Unsubscribe
    <a href="https://tldrnewsletter.com/unsub">구독 해지</a>
    </body></html>
    """
    body_region = extract_body_region(html, "dan@tldrnewsletter.com")

    links = extract_candidate_links(body_region)

    urls = [link.url for link in links]
    assert "https://example.com/article1" in urls
    assert "https://example.com/article2" in urls
    assert "https://tldrnewsletter.com/unsub" not in urls


def test_common_filters_exclude_unsubscribe_and_social_share():
    assert is_excluded_by_common_filters("https://site.com/unsubscribe?id=1")
    assert is_excluded_by_common_filters("https://twitter.com/intent/tweet?text=x")
    assert is_excluded_by_common_filters("https://facebook.com/share?u=x")
    assert not is_excluded_by_common_filters("https://example.com/real-article")


def test_select_top_links_caps_at_50_preserving_order():
    links = [RawLink(url=f"https://example.com/{i}", anchor_text=str(i), order=i) for i in range(60)]

    selected, cap_applied = select_top_links(links, cap=50)

    assert cap_applied is True
    assert len(selected) == 50
    assert [link.order for link in selected] == list(range(50))


def test_select_top_links_no_cap_when_under_limit():
    links = [RawLink(url=f"https://example.com/{i}", anchor_text=str(i), order=i) for i in range(10)]

    selected, cap_applied = select_top_links(links, cap=50)

    assert cap_applied is False
    assert len(selected) == 10


def test_normalize_url_strips_utm_params_and_fragment():
    url = "https://example.com/article/?utm_source=newsletter&utm_medium=email&id=5#section"
    assert normalize_url(url) == "https://example.com/article?id=5"


def test_normalize_url_equal_for_equivalent_urls_with_different_tracking():
    a = normalize_url("https://example.com/post?utm_source=tldr")
    b = normalize_url("https://example.com/post?utm_source=geeknews")
    assert a == b


@respx.mock
def test_resolve_redirect_follows_redirect_chain_to_final_url():
    respx.head("https://track.example.com/r/1").mock(
        return_value=httpx.Response(302, headers={"location": "https://track.example.com/r/2"})
    )
    respx.head("https://track.example.com/r/2").mock(
        return_value=httpx.Response(302, headers={"location": "https://final.example.com/article"})
    )
    respx.head("https://final.example.com/article").mock(return_value=httpx.Response(200))

    with httpx.Client() as client:
        resolved = resolve_redirect("https://track.example.com/r/1", client)

    assert resolved == "https://final.example.com/article"
