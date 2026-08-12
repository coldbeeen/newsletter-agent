"""일회성 진단 스크립트: TLDR 발신 주소의 IMAP FROM 검색이 실제로 메일을 찾는지 확인한다.
자격증명이나 메일 본문은 절대 출력하지 않고, 폴더명/건수/제목 길이 등 메타 정보만 로그로 남긴다.
"""
import os
import sys
from datetime import date, timedelta

from imap_tools import AND, MailBox

TARGET_ADDRESSES = [
    "dan@tldrnewsletter.com",
    "news@hada.io",
    "newsletter@mail.routinecrew.net",
]


def main() -> None:
    host = os.environ.get("NAVER_IMAP_HOST", "imap.naver.com")
    port = int(os.environ.get("NAVER_IMAP_PORT", "993"))
    user = os.environ["NAVER_IMAP_USER"]
    password = os.environ["NAVER_IMAP_APP_PASSWORD"]

    with MailBox(host, port=port).login(user, password) as mailbox:
        print("=== Folder list ===")
        for f in mailbox.folder.list():
            print(f"  {f.name!r} flags={f.flags}")

        current_folder = mailbox.folder.get()
        print(f"\n=== Currently selected folder: {current_folder!r} ===")

        since_7d = date.today() - timedelta(days=7)
        print(f"\n=== FULL fetch (same as pipeline) in current folder, SINCE {since_7d} ===")
        for addr in TARGET_ADDRESSES:
            query = AND(from_=addr, date_gte=since_7d)
            count = 0
            errors = 0
            try:
                for msg in mailbox.fetch(query, mark_seen=False):
                    count += 1
                    try:
                        display_name = msg.from_values.name if msg.from_values else ""
                        html_len = len(msg.html or msg.text or "")
                        print(
                            f"    ok date={msg.date} display_name={display_name!r} "
                            f"subject_len={len(msg.subject or '')} html_len={html_len}"
                        )
                    except Exception as inner_exc:
                        errors += 1
                        print(
                            f"    PARSE ERROR on message #{count}: "
                            f"{type(inner_exc).__name__}: {inner_exc}"
                        )
            except Exception as loop_exc:
                print(
                    f"  {addr}: LOOP RAISED after {count} messages: "
                    f"{type(loop_exc).__name__}: {loop_exc}"
                )
                continue
            print(f"  {addr}: {count} messages fully parsed, {errors} parse errors")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
