from pathlib import Path

from newsletter_agent.parsing.html_body import extract_body_region, extract_visible_text
from newsletter_agent.parsing.links import extract_candidate_links

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_extract_visible_text_strips_script_and_style():
    html = FIXTURES.joinpath("sample_body.html").read_text(encoding="utf-8")

    text = extract_visible_text(html)

    assert "console.log" not in text
    assert "color: red" not in text
    assert "Test Newsletter" not in text


def test_extract_visible_text_keeps_paragraph_content():
    html = FIXTURES.joinpath("sample_body.html").read_text(encoding="utf-8")

    text = extract_visible_text(html)

    assert "오늘의 기술 뉴스레터입니다." in text
    assert "AI 업계에 새로운 소식이 있습니다." in text


def test_footer_trim_keeps_article_links_in_table_layout_email():
    """TLDR처럼 <body><table>전체 콘텐츠</table></body> 구조인 이메일에서,
    footer marker(unsubscribe)가 테이블 맨 끝에 있어도 앞쪽 기사 링크가 살아남아야 한다."""
    html = """
    <html><body>
    <table>
      <tr><td><a href="https://example.com/article-1">첫 번째 기사</a></td></tr>
      <tr><td><a href="https://example.com/article-2">두 번째 기사</a></td></tr>
      <tr><td>Unsubscribe from this list</td></tr>
    </table>
    </body></html>
    """

    body_region = extract_body_region(html, "dan@tldrnewsletter.com")
    links = extract_candidate_links(body_region)

    urls = {link.url for link in links}
    assert "https://example.com/article-1" in urls
    assert "https://example.com/article-2" in urls
