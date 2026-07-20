from datetime import date

from freezegun import freeze_time

from newsletter_agent.mail.time_window import kst_today_window


@freeze_time("2026-07-20 05:00:00", tz_offset=0)  # 2026-07-20 14:00 KST
def test_kst_today_window_returns_yesterday_kst_date():
    assert kst_today_window() == date(2026, 7, 19)


@freeze_time("2026-07-19 15:30:00", tz_offset=0)  # 2026-07-20 00:30 KST (day boundary)
def test_kst_today_window_handles_day_boundary_crossing():
    assert kst_today_window() == date(2026, 7, 19)
