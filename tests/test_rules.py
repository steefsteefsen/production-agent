"""AI4I-Regelprüfung: Verifikations- und Falsifikationstests je Regel.

Tests: check_twf, check_hdf, check_pwf, check_osf, check_all, triggered_modes.
Wertebereiche aus decisions.yaml / UCI AI4I 2020.
"""

from __future__ import annotations

import math

from production_agent.graph.rules import (
    check_all,
    check_hdf,
    check_osf,
    check_pwf,
    check_twf,
    triggered_modes,
)

# ---------------------------------------------------------------------------
# TWF – Werkzeugverschleiß 200–240 min
# ---------------------------------------------------------------------------


def test_twf_im_bereich():
    """Verifikation: tool_wear=220 → TWF ausgelöst."""
    r = check_twf({"tool_wear": 220})
    assert r.triggered is True
    assert r.code == "TWF"


def test_twf_untergrenze():
    """Verifikation: tool_wear=200 → TWF ausgelöst (Grenze inklusive)."""
    assert check_twf({"tool_wear": 200}).triggered is True


def test_twf_obergrenze():
    """Verifikation: tool_wear=240 → TWF ausgelöst (Grenze inklusive)."""
    assert check_twf({"tool_wear": 240}).triggered is True


def test_twf_unter_bereich_falsification():
    """Falsifikation: tool_wear=199 → TWF NICHT ausgelöst."""
    assert check_twf({"tool_wear": 199}).triggered is False


def test_twf_ueber_bereich_falsification():
    """Falsifikation: tool_wear=241 → TWF NICHT ausgelöst (Verschleiß zu hoch)."""
    assert check_twf({"tool_wear": 241}).triggered is False


def test_twf_text_enthaelt_messwert():
    """Verifikation: RuleResult.text enthält den Messwert."""
    r = check_twf({"tool_wear": 215})
    assert "215" in r.text


# ---------------------------------------------------------------------------
# HDF – Prozess-Luft-Delta < 8.6 K UND rpm < 1380
# ---------------------------------------------------------------------------


def test_hdf_beide_bedingungen():
    """Verifikation: Δtemp=7 K und rpm=1200 → HDF ausgelöst."""
    snap = {"process_temp": 307.0, "air_temp": 300.0, "rpm": 1200}
    assert check_hdf(snap).triggered is True


def test_hdf_genau_grenze():
    """Verifikation: Δtemp=8.5 K und rpm=1379 → HDF ausgelöst (beide Grenzen knapp erfüllt)."""
    snap = {"process_temp": 308.5, "air_temp": 300.0, "rpm": 1379}
    assert check_hdf(snap).triggered is True


def test_hdf_delta_zu_gross_falsification():
    """Falsifikation: Δtemp=9 K → HDF NICHT ausgelöst."""
    snap = {"process_temp": 309.0, "air_temp": 300.0, "rpm": 1200}
    assert check_hdf(snap).triggered is False


def test_hdf_rpm_zu_hoch_falsification():
    """Falsifikation: rpm=1380 → HDF NICHT ausgelöst (Grenze exklusiv oben)."""
    snap = {"process_temp": 307.0, "air_temp": 300.0, "rpm": 1380}
    assert check_hdf(snap).triggered is False


def test_hdf_beide_bedingungen_fehlen_falsification():
    """Falsifikation: Δtemp=10 K und rpm=2000 → HDF NICHT ausgelöst."""
    snap = {"process_temp": 310.0, "air_temp": 300.0, "rpm": 2000}
    assert check_hdf(snap).triggered is False


# ---------------------------------------------------------------------------
# PWF – Leistung außerhalb [3500 W, 9000 W]
# ---------------------------------------------------------------------------


def _power_snap(torque: float, rpm: float) -> dict:
    return {"torque": torque, "rpm": rpm}


def test_pwf_zu_niedrig():
    """Verifikation: P ≈ 1047 W (Torque=10, rpm=1000) → PWF ausgelöst."""
    snap = _power_snap(torque=10.0, rpm=1000.0)
    p = 10.0 * 1000.0 * 2 * math.pi / 60
    assert p < 3500
    assert check_pwf(snap).triggered is True


def test_pwf_zu_hoch():
    """Verifikation: P = torque·rpm·2π/60 > 9000 W → PWF ausgelöst."""
    # rpm=2600, torque=60 → P ≈ 16336 W
    snap = _power_snap(torque=60.0, rpm=2600.0)
    p = 60.0 * 2600.0 * 2 * math.pi / 60
    assert p > 9000
    assert check_pwf(snap).triggered is True


def test_pwf_im_erlaubten_bereich_falsification():
    """Falsifikation: Normalbetrieb (torque=40, rpm=1540) → PWF NICHT ausgelöst."""
    snap = _power_snap(torque=40.0, rpm=1540.0)
    p = 40.0 * 1540.0 * 2 * math.pi / 60
    assert 3500 <= p <= 9000
    assert check_pwf(snap).triggered is False


def test_pwf_text_enthaelt_leistung():
    """Verifikation: RuleResult.text enthält berechnete Leistung in Watt."""
    snap = _power_snap(torque=10.0, rpm=1000.0)
    r = check_pwf(snap)
    assert "W" in r.text


# ---------------------------------------------------------------------------
# OSF – Werkzeugverschleiß × Drehmoment > Schwelle (L/M/H)
# ---------------------------------------------------------------------------


def test_osf_typ_l():
    """Verifikation: L-Linie, 180 min × 65 Nm = 11700 > 11000 → OSF ausgelöst."""
    snap = {"type": "L", "tool_wear": 180, "torque": 65.0}
    assert check_osf(snap).triggered is True


def test_osf_typ_m():
    """Verifikation: M-Linie, 200 min × 65 Nm = 13000 > 12000 → OSF ausgelöst."""
    snap = {"type": "M", "tool_wear": 200, "torque": 65.0}
    assert check_osf(snap).triggered is True


def test_osf_typ_h():
    """Verifikation: H-Linie, 210 min × 65 Nm = 13650 > 13000 → OSF ausgelöst."""
    snap = {"type": "H", "tool_wear": 210, "torque": 65.0}
    assert check_osf(snap).triggered is True


def test_osf_l_unter_schwelle_falsification():
    """Falsifikation: L-Linie, 100 min × 50 Nm = 5000 ≤ 11000 → OSF NICHT ausgelöst."""
    snap = {"type": "L", "tool_wear": 100, "torque": 50.0}
    assert check_osf(snap).triggered is False


def test_osf_h_knapp_unter_schwelle_falsification():
    """Falsifikation: H-Linie, 200 min × 65 Nm = 13000 ≤ 13000 → OSF NICHT ausgelöst (Grenze)."""
    snap = {"type": "H", "tool_wear": 200, "torque": 65.0}
    assert check_osf(snap).triggered is False


def test_osf_unbekannter_typ_fallback():
    """Verifikation: Unbekannter Typ → Fallback auf M-Schwelle (12000)."""
    snap = {"type": "X", "tool_wear": 200, "torque": 61.0}
    # 200 × 61 = 12200 > 12000 → ausgelöst
    assert check_osf(snap).triggered is True


# ---------------------------------------------------------------------------
# check_all / triggered_modes
# ---------------------------------------------------------------------------


def test_check_all_liefert_vier_ergebnisse():
    """Verifikation: check_all gibt immer genau 4 RuleResult-Objekte zurück."""
    snap = {
        "type": "M",
        "air_temp": 300,
        "process_temp": 310,
        "rpm": 1540,
        "torque": 40,
        "tool_wear": 100,
    }
    results = check_all(snap)
    assert len(results) == 4
    codes = [r.code for r in results]
    assert codes == ["TWF", "HDF", "PWF", "OSF"]


def test_check_all_kein_trigger_normalzustand():
    """Verifikation: Normal-Snapshot (kein Fail-Modus) → keine Regel ausgelöst."""
    snap = {
        "type": "M",
        "air_temp": 300,
        "process_temp": 310,
        "rpm": 1540,
        "torque": 40,
        "tool_wear": 100,
    }
    results = check_all(snap)
    assert not any(r.triggered for r in results)


def test_triggered_modes_sto_antrieb():
    """Verifikation: STO-ANTRIEB-Snapshot (hoher Verschleiß + hohes Drehmoment) → TWF+OSF."""
    snap = {
        "type": "M",
        "air_temp": 300,
        "process_temp": 310,
        "rpm": 1540,
        "torque": 65.0,
        "tool_wear": 220,
    }
    codes, texts = triggered_modes(snap)
    assert "TWF" in codes
    assert "OSF" in codes
    assert len(texts) == len(codes)


def test_triggered_modes_sto_elek():
    """Verifikation: STO-ELEK-Snapshot (hohe Drehzahl + hohes Drehmoment) → PWF."""
    snap = {
        "type": "M",
        "air_temp": 300,
        "process_temp": 310,
        "rpm": 2600,
        "torque": 60.0,
        "tool_wear": 50,
    }
    codes, texts = triggered_modes(snap)
    assert "PWF" in codes
    assert all(isinstance(t, str) and t for t in texts)


def test_triggered_modes_leer_falsification():
    """Falsifikation: leerer Snapshot → keine Regel ausgelöst (kein Absturz)."""
    codes, texts = triggered_modes({})
    assert isinstance(codes, list)
    assert codes == []
    assert texts == []


def test_check_all_drei_ausgeloest():
    """Verifikation: Snapshot mit TWF + HDF + OSF ausgelöst (PWF ∈ Normalbereich)."""
    # TWF: wear=220 ∈ [200,240]; HDF: Δtemp=7 < 8.6, rpm=1200 < 1380
    # PWF: P = 65*1200*2π/60 ≈ 8168 ∈ [3500,9000] → nicht ausgelöst
    # OSF: L, 220*65=14300 > 11000 ✓
    snap = {
        "type": "L",
        "air_temp": 300,
        "process_temp": 307,
        "rpm": 1200,
        "torque": 65.0,
        "tool_wear": 220,
    }
    results = check_all(snap)
    triggered = {r.code for r in results if r.triggered}
    assert "TWF" in triggered
    assert "HDF" in triggered
    assert "OSF" in triggered
