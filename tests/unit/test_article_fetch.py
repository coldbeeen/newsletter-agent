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
