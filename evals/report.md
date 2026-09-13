# Replay-Eval – Bericht

Erzeugt von `evals/run_evals.py` aus einem echten Graph-Lauf je Replay-Fall (LLM-Modus: mock (deterministisches Mock-LLM)). Grundlage: ADR-0002 – Historie und aktueller Fall stammen aus derselben Verteilung; die Gold-Zeile ist die für den Agenten unsichtbare Wahrheit.

> Ehrlichkeitsgrenze: Der Simulator kennt seine eigenen Ursachen. Trefferquote und Dauerfehler sind eine **Obergrenze**, kein Feldwert. Dies ist MLOps-light (kein Drift-Monitoring, kein Retraining).

## Kennzahlen

- Fälle: 10
- Ursachen-Trefferquote (reason_hit): 100% (10/10)
- Ø absoluter Dauerfehler: 6.7 min
- Fälle mit allen deterministischen Prüfungen grün: 10/10

## Fälle

| event_id | Linie | gold | vorhergesagt | reason_hit | Dauerfehler (min) | Konfidenz | Schranke | Flut | Prüfungen |
|---|---|---|---|---|---|---|---|---|---|
| 351 | L1 | STO-SIEGEL | STO-SIEGEL | ja | 12.1 | 0.80 | 1.00 | nein | alle grün |
| 352 | L1 | MAT-LEER | MAT-LEER | ja | 1.7 | 0.80 | 1.00 | nein | alle grün |
| 353 | L1 | QUAL-NIO | QUAL-NIO | ja | 6.0 | 0.80 | 1.00 | nein | alle grün |
| 354 | L1 | STO-SENSOR | STO-SENSOR | ja | 2.3 | 0.80 | 1.00 | ja | alle grün |
| 355 | L1 | QUAL-HOLD | QUAL-HOLD | ja | 13.1 | 0.80 | 1.00 | nein | alle grün |
| 356 | L1 | STO-FOLIE | STO-FOLIE | ja | 3.7 | 0.80 | 1.00 | ja | alle grün |
| 357 | L1 | STO-ELEK | STO-ELEK | ja | 13.5 | 0.80 | 1.00 | nein | alle grün |
| 358 | L1 | STO-FOLIE | STO-FOLIE | ja | 6.7 | 0.80 | 1.00 | ja | alle grün |
| 359 | L1 | MAT-LEER | MAT-LEER | ja | 1.8 | 0.80 | 1.00 | nein | alle grün |
| 360 | L1 | STO-FOLIE | STO-FOLIE | ja | 5.7 | 0.80 | 1.00 | ja | alle grün |

## Deterministische Prüfungen (je Fall)

| Prüfung | grün | von |
|---|---|---|
| interrupt_erreicht | 10 | 10 |
| keine_forbidden_massnahme | 10 | 10 |
| konfidenz_le_formel | 10 | 10 |
| alarmflut_rag_zweig | 10 | 10 |
| werkzeugreihenfolge | 10 | 10 |

## Konfusionsmatrix Ursache (gold → vorhergesagt)

| gold_reason_code | vorhergesagt | Anzahl |
|---|---|---|
| MAT-LEER | MAT-LEER  | 2 |
| QUAL-HOLD | QUAL-HOLD  | 1 |
| QUAL-NIO | QUAL-NIO  | 1 |
| STO-ELEK | STO-ELEK  | 1 |
| STO-FOLIE | STO-FOLIE  | 3 |
| STO-SENSOR | STO-SENSOR  | 1 |
| STO-SIEGEL | STO-SIEGEL  | 1 |

*) Zeilen mit Stern: Fehlklassifikation (gold ≠ vorhergesagt).
