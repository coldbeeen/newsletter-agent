from collections.abc import Iterable
from datetime import date

from imap_tools import AND, MailBox
from imap_tools.errors import MailboxLoginError

from newsletter_agent.models import EmailMessage


class ImapAuthenticationFailed(Exception):
    """IMAP 인증 실패. 계정 잠금 방지를 위해 재시도하지 않고 즉시 전파한다."""


class MailClient:
    def __init__(self, host: str, port: int, user: str, password: str):
        self._host = host
        self._port = port
        self._user = user
        self._password = password

    def fetch_recent(
        self, sender_addresses: Iterable[str], since_date_kst: date
    ) -> list[EmailMessage]:
        messages: list[EmailMessage] = []
        try:
            mailbox_ctx = MailBox(self._host, port=self._port).login(
                self._user, self._password
            )
        except MailboxLoginError as exc:
            raise ImapAuthenticationFailed(str(exc)) from exc

        with mailbox_ctx as mailbox:
            for addr in sender_addresses:
                for msg in mailbox.fetch(AND(from_=addr, date_gte=since_date_kst)):
                    messages.append(
                        EmailMessage(
                            msg_id=msg.uid or msg.headers.get("message-id", [""])[0],
                            from_addr=addr,
                            from_display_name=msg.from_values.name if msg.from_values else "",
                            subject=msg.subject,
                            received_at=msg.date,
                            html_body=msg.html or msg.text or "",
                        )
                    )
        return messages
