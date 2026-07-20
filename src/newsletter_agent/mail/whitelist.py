from dataclasses import dataclass
from pathlib import Path

import yaml

from newsletter_agent.logging_config import get_logger
from newsletter_agent.models import NewsletterId

logger = get_logger(__name__)


@dataclass(frozen=True)
class _NewsletterRule:
    name: str
    display_names: tuple[str, ...]


class Whitelist:
    def __init__(self, senders: dict[str, list[_NewsletterRule]]):
        self._senders = senders

    @classmethod
    def load(cls, path: str | Path) -> "Whitelist":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        senders: dict[str, list[_NewsletterRule]] = {}
        for sender in data.get("senders", []):
            address = sender["address"].strip().lower()
            rules = [
                _NewsletterRule(
                    name=nl["name"],
                    display_names=tuple(nl.get("display_names") or []),
                )
                for nl in sender.get("newsletters", [])
            ]
            senders[address] = rules
        return cls(senders)

    def addresses(self) -> set[str]:
        return set(self._senders.keys())

    def classify(self, from_addr: str, from_display_name: str) -> NewsletterId:
        address = from_addr.strip().lower()
        rules = self._senders.get(address)
        if not rules:
            # 화이트리스트에 없는 주소는 상위 계층(fetch_recent)에서 이미 걸러지지만,
            # 방어적으로 미분류 처리한다.
            logger.warning("Address not in whitelist: %s", from_addr)
            return NewsletterId(name="미분류", matched=False)

        # 주소 단독으로 식별 가능한 경우 (display_names 미지정)
        if len(rules) == 1 and not rules[0].display_names:
            return NewsletterId(name=rules[0].name, matched=True)

        display_name = from_display_name.strip()
        for rule in rules:
            if display_name in rule.display_names:
                return NewsletterId(name=rule.name, matched=True)

        fallback_name = f"{_group_fallback_label(rules)}(미분류)"
        logger.warning(
            "Unrecognized display name %r for address %s; falling back to %s",
            from_display_name,
            from_addr,
            fallback_name,
        )
        return NewsletterId(name=fallback_name, matched=False)


def _group_fallback_label(rules: list[_NewsletterRule]) -> str:
    # 스펙 예시(TLDR 계열)에 맞춰, 규칙 이름들의 공통 접두어를 폴백 라벨로 사용.
    names = [rule.name for rule in rules]
    first_word = names[0].split()[0]
    if all(name.split()[0] == first_word for name in names):
        return first_word
    return "뉴스레터"
