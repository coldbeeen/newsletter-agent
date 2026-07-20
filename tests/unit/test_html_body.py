from pathlib import Path

from newsletter_agent.parsing.html_body import extract_visible_text

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
