# Indice della documentazione

Mappa moduli → sorgenti → documento (GOLDEN_STD §0). Leggere i documenti prima del codice.

| Modulo | Sorgenti | Documento |
|---|---|---|
| Interfaccia Streamlit | `app.py` | [modules/app.md](modules/app.md) |
| Accesso hardware | `dats/hardware.py` | [modules/dats/hardware.md](modules/dats/hardware.md) |
| Segnali e misura | `dats/dsp.py` | [modules/dats/dsp.md](modules/dats/dsp.md) |
| Calibrazione | `dats/calibration.py` | [modules/dats/calibration.md](modules/dats/calibration.md) |
| Parametri | `dats/params.py` | [modules/dats/params.md](modules/dats/params.md) |
| Export / import | `dats/export.py` | [modules/dats/export.md](modules/dats/export.md) |
| Versione del pacchetto | `dats/__init__.py`, `VERSION` | [../CHANGELOG.md](../CHANGELOG.md) |
| Test | `tests/test_dats.py` | questo indice, sezione Test |

## Dipendenze fra moduli

```
app.py ──> hardware, dsp, calibration, params, export
dsp ─────> hardware
calibration, params ──> dsp (frac_octave_smooth)
export ──> (solo numpy)
```

Nessuna dipendenza circolare. Solo `hardware` parla con PortAudio; solo `app.py` usa Streamlit e Plotly.

## Test

```bash
python -m unittest discover -s tests -v
```

La suite gira senza hardware: modelli sintetici di driver e componenti, calibrazione Open/Short/Load
simulata, regressione su `Exported Impedance Data.txt` (export del DATS originale) e smoke test
headless dell'interfaccia con `streamlit.testing.v1.AppTest`.
Le misure reali richiedono il DATS collegato e restano manuali (vedi i documenti dei moduli).
