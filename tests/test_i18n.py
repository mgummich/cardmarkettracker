import re

import pytest
from i18n_tools import all_msgids

from cmtracker.formatting import eur, local_time, pct
from cmtracker.i18n import _, get_language, language, negotiate, set_language
from cmtracker.locales.de import MESSAGES

# looked up dynamically (not as a literal _("…") call)
DYNAMIC = {"Private", "Professional", "Powerseller", "Check running"}


def test_every_string_has_a_german_translation():
    missing = {k: v for k, v in all_msgids().items() if k not in MESSAGES}
    assert not missing, "untranslated strings:\n" + "\n".join(
        f"  {where}: {msg!r}" for msg, where in missing.items()
    )


def test_no_stale_translations():
    stale = set(MESSAGES) - set(all_msgids()) - DYNAMIC
    assert not stale, f"translations without source string: {sorted(stale)}"


@pytest.mark.parametrize("msgid", sorted(MESSAGES))
def test_placeholders_match(msgid):
    pattern = re.compile(r"\{[a-z_0-9]*\}|%[sd]")
    assert sorted(pattern.findall(msgid)) == sorted(pattern.findall(MESSAGES[msgid]))


def test_switching_and_fallback():
    with language("de"):
        assert _("Save") == "Speichern"
        assert get_language() == "de"
    with language("en"):
        assert _("Save") == "Save"
    with language("xx"):
        assert get_language() == "en"
    assert _("not in any catalog") == "not in any catalog"
    set_language("en")


def test_number_and_date_formats():
    from datetime import UTC, datetime

    dt = datetime(2026, 10, 31, 18, 5, tzinfo=UTC)
    with language("en"):
        assert eur(1234.5) == "€1,234.50"
        assert pct(-3.25) == "-3.2%"
        assert local_time(dt, "Europe/Berlin") == "2026-10-31 19:05"
    with language("de"):
        assert eur(1234.5) == "1.234,50 €"
        assert pct(-3.25) == "-3,2 %"
        assert local_time(dt, "Europe/Berlin") == "31.10.2026 19:05"


@pytest.mark.parametrize(
    "header,expected",
    [
        ("de-DE,de;q=0.9,en;q=0.8", "de"),
        ("en-US,en;q=0.9", "en"),
        ("fr-FR,fr;q=0.9,de;q=0.5,en;q=0.7", "en"),
        ("fr-FR", None),
        ("", None),
        (None, None),
        ("de;q=0", None),
    ],
)
def test_accept_language(header, expected):
    assert negotiate(header) == expected
