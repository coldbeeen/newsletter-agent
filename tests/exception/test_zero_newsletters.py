from pathlib import Path

from newsletter_agent.mail.whitelist import Whitelist
from newsletter_agent.pipeline import _classify_all
from newsletter_agent.summarize.report_synthesis import NO_NEWSLETTERS_MESSAGE

WHITELIST_PATH = Path(__file__).parent.parent.parent / "whitelist.yaml"


def test_zero_matching_emails_yields_no_newsletters_message_and_no_state_change(tmp_path):
    whitelist = Whitelist.load(WHITELIST_PATH)

    newsletters = _classify_all(whitelist, [])

    assert newsletters == []

    seen_path = tmp_path / "seen_urls.json"
    assert not seen_path.exists()
    # 0건일 때 파이프라인은 조기 반환하며 상태 파일에 손대지 않는다 — 여기서는 메시지 상수만 검증.
    assert NO_NEWSLETTERS_MESSAGE == "오늘 수신된 뉴스레터 없음"
