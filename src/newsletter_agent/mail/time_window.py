from datetime import date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def kst_today_window(now: datetime | None = None) -> date:
    """어제 날짜(KST)를 반환한다. IMAP SINCE 검색 기준일로 사용."""
    current = (now or datetime.now(tz=timezone.utc)).astimezone(KST)
    return (current - timedelta(days=1)).date()
