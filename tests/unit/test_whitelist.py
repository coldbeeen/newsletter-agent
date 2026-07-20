from pathlib import Path

from newsletter_agent.mail.whitelist import Whitelist

WHITELIST_PATH = Path(__file__).parent.parent.parent / "whitelist.yaml"


def _load() -> Whitelist:
    return Whitelist.load(WHITELIST_PATH)


def test_addresses_include_all_whitelisted_senders():
    whitelist = _load()

    addresses = whitelist.addresses()

    assert "dan@tldrnewsletter.com" in addresses
    assert "news@hada.io" in addresses
    assert "newsletter@mail.routinecrew.net" in addresses


def test_classify_tldr_variants_by_display_name():
    whitelist = _load()

    assert whitelist.classify("dan@tldrnewsletter.com", "TLDR AI").name == "TLDR AI"
    assert whitelist.classify("dan@tldrnewsletter.com", "TLDR IT").name == "TLDR IT"
    assert (
        whitelist.classify("dan@tldrnewsletter.com", "TLDR Marketing").name
        == "TLDR Marketing"
    )
    assert whitelist.classify("dan@tldrnewsletter.com", "TLDR Data").name == "TLDR Data"
    assert whitelist.classify("dan@tldrnewsletter.com", "TLDR").name == "TLDR"


def test_classify_unrecognized_display_name_falls_back_without_raising():
    whitelist = _load()

    result = whitelist.classify("dan@tldrnewsletter.com", "TLDR Something Weird")

    assert result.name == "TLDR(미분류)"
    assert result.matched is False


def test_classify_geeknews_and_routinecrew_by_address_alone():
    whitelist = _load()

    geeknews = whitelist.classify("news@hada.io", "")
    routinecrew = whitelist.classify("newsletter@mail.routinecrew.net", "Newsletter")

    assert geeknews.name == "GeekNews Weekly"
    assert geeknews.matched is True
    assert routinecrew.name == "Newsletter"
    assert routinecrew.matched is True


def test_classify_address_not_in_whitelist_is_unclassified():
    whitelist = _load()

    result = whitelist.classify("someone@random.com", "Random")

    assert result.matched is False
