"""decisions.yaml – Stefans Fachentscheidungen: 14 Codes, Schwelle, Kosten, configurable-Optionen."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEC = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
OEE_TYPES = {"availability", "performance", "quality"}


def check_reason_codes(codes) -> list[str]:
    """Prüffunktion: jeder reason_code braucht einen gültigen OEE-Verlusttyp."""
    errs = []
    for row in codes:
        code, _cat, _desc, loss = row
        if loss not in OEE_TYPES:
            errs.append(f"{code}: OEE-Typ '{loss}' ungültig")
    return errs


def test_14_reason_codes_with_valid_oee_type():
    assert len(DEC["reason_codes"]) == 14
    assert check_reason_codes(DEC["reason_codes"]) == []


def test_threshold_and_cost():
    assert DEC["konfidenz"]["schwelle_empfehlung"] == 0.60
    assert DEC["linie"]["cost_per_downtime_minute_eur"] == 200


def test_configurable_fields_have_at_least_two_options():
    assert len(DEC["alarm_prioritaet"]["verfahren_optionen"]) >= 2
    assert len(DEC["audit"]["personenbezug_optionen"]) >= 2


def test_code_without_oee_type_is_red_falsification():
    assert check_reason_codes([["X-BAD", "Stoerung", "ohne OEE-Typ", "kaputt"]])


def test_negative_kurzstillstand_is_red_falsification():
    def valid_kurz(v) -> bool:
        return isinstance(v, int | float) and v >= 0

    assert valid_kurz(DEC["ereignis"]["kurzstillstand_min"]) is True
    assert valid_kurz(-1) is False
