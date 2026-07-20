import json
from datetime import date

from newsletter_agent.dedup.seen_store import SeenStore
from newsletter_agent.models import Article, ArticleSummary, NewsletterId
from newsletter_agent.parsing.article_fetch import FetchResult


def _make_article(url: str) -> Article:
    return Article(
        url=url,
        normalized_url=url,
        title="제목",
        excerpt="발췌",
        fetch_result=FetchResult(status="ok", text="본문", reason="ok"),
        summary=ArticleSummary(text="요약", topic="AI"),
        source_newsletters=[NewsletterId(name="TLDR AI")],
    )


def test_load_save_round_trip(tmp_path):
    path = tmp_path / "seen_urls.json"
    store = SeenStore({})
    store.record([_make_article("https://example.com/a")], date(2026, 7, 19))
    store.save(path)

    reloaded = SeenStore.load(path)

    assert reloaded.filter_new([_make_article("https://example.com/a")]) == []
    assert len(reloaded.filter_new([_make_article("https://example.com/b")])) == 1


def test_filter_new_excludes_url_seen_on_prior_day():
    store = SeenStore({"https://example.com/old": "2026-07-19"})

    result = store.filter_new([_make_article("https://example.com/old")])

    assert result == []


def test_prune_removes_entries_older_than_retention_keeps_recent():
    store = SeenStore(
        {
            "https://example.com/old": "2026-06-01",
            "https://example.com/recent": "2026-07-15",
        }
    )

    store.prune(retention_days=30, today=date(2026, 7, 20))

    assert store.filter_new([_make_article("https://example.com/old")]) != []
    assert store.filter_new([_make_article("https://example.com/recent")]) == []


def test_save_writes_valid_json_via_atomic_write(tmp_path):
    path = tmp_path / "nested" / "seen_urls.json"
    store = SeenStore({})
    store.record([_make_article("https://example.com/a")], date(2026, 7, 19))

    store.save(path)

    assert path.exists()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["urls"]["https://example.com/a"] == "2026-07-19"
    # 임시파일이 남아있지 않아야 한다.
    leftover_tmp_files = list(path.parent.glob(".*.tmp"))
    assert leftover_tmp_files == []
