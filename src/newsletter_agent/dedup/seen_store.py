import json
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from newsletter_agent.models import Article


class SeenStore:
    def __init__(self, urls: dict[str, str]):
        self._urls = urls

    @classmethod
    def load(cls, path: str | Path) -> "SeenStore":
        path = Path(path)
        if not path.exists():
            return cls({})
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(dict(data.get("urls", {})))

    def filter_new(self, articles: list[Article]) -> list[Article]:
        return [a for a in articles if a.normalized_url not in self._urls]

    def record(self, articles: list[Article], today: date) -> None:
        today_str = today.isoformat()
        for article in articles:
            self._urls[article.normalized_url] = today_str

    def prune(self, retention_days: int, today: date | None = None) -> None:
        cutoff = (today or datetime.now(tz=UTC).date()) - timedelta(days=retention_days)
        self._urls = {
            url: seen_date
            for url, seen_date in self._urls.items()
            if date.fromisoformat(seen_date) >= cutoff
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"urls": self._urls}

        fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
