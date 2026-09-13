"""AI4I-Ausfallmodus-Regeln als reine Funktionen über einen Sensor-Snapshot.

Quelle: UCI-Datensatz AI4I 2020, CC BY 4.0 (id 601).
Alle vier Modi: TWF, HDF, PWF, OSF – Wertebereiche nach decisions.yaml / ADR-0002.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_OSF_THRESHOLD: dict[str, float] = {"L": 11000.0, "M": 12000.0, "H": 13000.0}

NUM_RULES = 4


@dataclass(frozen=True)
class RuleResult:
    """Ergebnis einer einzelnen AI4I-Regelprüfung."""

    code: str
    triggered: bool
    text: str


def check_twf(snapshot: dict) -> RuleResult:
    """TWF: Werkzeugverschleiß im Bereich 200–240 min."""
    wear = float(snapshot.get("tool_wear", 0.0))
    triggered = 200.0 <= wear <= 240.0
    direction = "∈" if triggered else "∉"
    return RuleResult(
        code="TWF",
        triggered=triggered,
        text=f"TWF: tool_wear={wear:.0f} min {direction} [200, 240]",
    )


def check_hdf(snapshot: dict) -> RuleResult:
    """HDF: Prozess-Luft-Temperaturdifferenz < 8.6 K und Drehzahl < 1380 rpm."""
    _required = {"process_temp", "air_temp", "rpm"}
    if not _required.issubset(snapshot):
        return RuleResult(code="HDF", triggered=False, text="HDF: Sensordaten fehlen")
    process_temp = float(snapshot["process_temp"])
    air_temp = float(snapshot["air_temp"])
    delta_t = process_temp - air_temp
    rpm = float(snapshot["rpm"])
    triggered = delta_t < 8.6 and rpm < 1380.0
    return RuleResult(
        code="HDF",
        triggered=triggered,
        text=(
            f"HDF: Δtemp={delta_t:.1f} K (<8.6?{'j' if delta_t < 8.6 else 'n'}), "
            f"rpm={rpm:.0f} (<1380?{'j' if rpm < 1380.0 else 'n'})"
        ),
    )


def check_pwf(snapshot: dict) -> RuleResult:
    """PWF: Leistung torque·rpm·2π/60 außerhalb [3500 W, 9000 W]."""
    _required = {"torque", "rpm"}
    if not _required.issubset(snapshot):
        return RuleResult(code="PWF", triggered=False, text="PWF: Sensordaten fehlen")
    torque = float(snapshot["torque"])
    rpm = float(snapshot["rpm"])
    power_w = torque * rpm * 2.0 * math.pi / 60.0
    triggered = power_w < 3500.0 or power_w > 9000.0
    if power_w < 3500.0:
        detail = f"{power_w:.0f} W < 3500"
    elif power_w > 9000.0:
        detail = f"{power_w:.0f} W > 9000"
    else:
        detail = f"{power_w:.0f} W ∈ [3500, 9000]"
    return RuleResult(code="PWF", triggered=triggered, text=f"PWF: P={detail}")


def check_osf(snapshot: dict) -> RuleResult:
    """OSF: tool_wear · torque > Schwelle je Produkttyp (L=11000, M=12000, H=13000)."""
    typ = str(snapshot.get("type", "M")).upper()
    wear = float(snapshot.get("tool_wear", 0.0))
    torque = float(snapshot.get("torque", 0.0))
    threshold = _OSF_THRESHOLD.get(typ, _OSF_THRESHOLD["M"])
    product = wear * torque
    triggered = product > threshold
    return RuleResult(
        code="OSF",
        triggered=triggered,
        text=(
            f"OSF: {wear:.0f} min × {torque:.1f} Nm = {product:.0f} "
            f"{'>' if triggered else '≤'} {threshold:.0f} (Typ {typ})"
        ),
    )


def check_all(snapshot: dict) -> list[RuleResult]:
    """Alle vier AI4I-Regeln auswerten. Reihenfolge: TWF, HDF, PWF, OSF."""
    return [check_twf(snapshot), check_hdf(snapshot), check_pwf(snapshot), check_osf(snapshot)]


def triggered_modes(snapshot: dict) -> tuple[list[str], list[str]]:
    """Ausgelöste Regelcodes und Regeltext-Liste zurückgeben.

    Returns:
        codes: ausgelöste Regelcodes (z. B. ["TWF", "OSF"])
        texts: menschenlesbarer Regeltext je ausgelöstem Modus
    """
    results = check_all(snapshot)
    codes = [r.code for r in results if r.triggered]
    texts = [r.text for r in results if r.triggered]
    return codes, texts
