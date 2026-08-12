import httpx
import respx

from newsletter_agent.parsing.article_fetch import fetch_article


@respx.mock
def test_fetch_article_404_classified_as_not_found():
    respx.get("https://example.com/missing").mock(return_value=httpx.Response(404))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/missing", client)

    assert result.status == "not_found"
    assert result.reason == "404"
    assert result.text is None


@respx.mock
def test_fetch_article_timeout_classified_as_not_found():
    respx.get("https://example.com/slow").mock(side_effect=httpx.TimeoutException("timed out"))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/slow", client)

    assert result.status == "not_found"
    assert result.reason == "timeout"


@respx.mock
def test_fetch_article_403_classified_as_blocked():
    respx.get("https://example.com/blocked").mock(return_value=httpx.Response(403))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/blocked", client)

    assert result.status == "blocked"
    assert result.reason == "403"


@respx.mock
def test_fetch_article_cloudflare_marker_classified_as_blocked():
    html = "<html><body>Checking your browser before accessing... Cloudflare</body></html>"
    respx.get("https://example.com/cf").mock(return_value=httpx.Response(200, text=html))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/cf", client)

    assert result.status == "blocked"
    assert result.reason == "bot_detection_marker"


@respx.mock
def test_fetch_article_about_cloudflare_topic_not_classified_as_blocked():
    """본문이 Cloudflare/CAPTCHA를 '주제로 다루는' 정상 기사인 경우, 실제 차단 문구
    (checking your browser, access denied 등)가 없다면 봇 차단으로 오판하면 안 된다."""
    html = """
    <html><body>
    <article>
      <p>Cloudflare WAF에서 국가/UA/ASN 조합으로 차단 또는 Managed Challenge를 적용했다.</p>
      <p>최근 48시간의 CAPTCHA 106,437건 중 252건만 성공해 0.24% solve rate를 기록했다.</p>
    </article>
    </body></html>
    """
    respx.get("https://example.com/about-cf").mock(return_value=httpx.Response(200, text=html))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/about-cf", client)

    assert result.status == "ok"
    assert "Cloudflare WAF" in result.text


@respx.mock
def test_fetch_article_hada_topic_page_follows_to_original_article():
    """GeekNews(hada.io) 뉴스레터 링크는 원문이 아니라 hada.io 자체 토픽(코멘트) 페이지를
    가리킨다. 그 페이지 안의 원문 링크(class="topic-title-link")를 따라가 실제 기사를
    fetch해야 한다."""
    topic_html = """
    <html><body>
    <h2><a href="https://example.com/original-article" class="bold ud topic-title-link">
      원문 기사 제목
    </a></h2>
    <div class="topic-desc">hada.io 커뮤니티의 요약/코멘트 내용입니다.</div>
    </body></html>
    """
    original_html = """
    <html><body>
    <article>
      <p>이것은 원문 기사의 첫 번째 문단입니다.</p>
      <p>이것은 원문 기사의 두 번째 문단입니다.</p>
    </article>
    </body></html>
    """
    respx.get("https://news.hada.io/topic?id=99999").mock(
        return_value=httpx.Response(200, text=topic_html)
    )
    respx.get("https://example.com/original-article").mock(
        return_value=httpx.Response(200, text=original_html)
    )

    with httpx.Client() as client:
        result = fetch_article("https://news.hada.io/topic?id=99999", client)

    assert result.status == "ok"
    assert "원문 기사의 첫 번째 문단" in result.text
    assert "커뮤니티의 요약" not in result.text


@respx.mock
def test_fetch_article_success_extracts_nonempty_text():
    html = """
    <html><body>
    <article>
      <p>이것은 첫 번째 문단입니다.</p>
      <p>이것은 두 번째 문단입니다.</p>
    </article>
    </body></html>
    """
    respx.get("https://example.com/ok").mock(return_value=httpx.Response(200, text=html))

    with httpx.Client() as client:
        result = fetch_article("https://example.com/ok", client)

    assert result.status == "ok"
    assert result.reason == "ok"
    assert "첫 번째 문단" in result.text
    assert "두 번째 문단" in result.text
