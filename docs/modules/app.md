# app.py — interfaccia Streamlit

Sorgenti: `app.py`

Unica parte che usa Streamlit e Plotly. Non contiene calcoli di misura: chiama `dsp`, `calibration`,
`params`, `export`, `hardware`.

## Struttura

- **Barra laterale**: dispositivi (rilevati con `hardware.find_dats_devices`), frequenza di
  campionamento, inversione canali, risoluzione (`dsp.QUALITY`), segnale di test (`dsp.EXCITATIONS`),
  livello, opzioni del grafico, stato della calibrazione, versione (`dats.__version__`).
- **Schede**: Impedenza/T-S (con Vas), R·L·C, Linearità, Rub & Buzz, Memorie, Generatore/Scope,
  Calibrazione.
- `run_raw()` esegue una misura; se l'ingresso satura ripete 6 dB più in basso (fino a 3 volte),
  poi avvisa. `run_measure()` applica la calibrazione.

## Stato di sessione

| Chiave | Contenuto |
|---|---|
| `cal` | `Calibration` caricata da disco, salvata a ogni passo di calibrazione |
| `memories` | lista di misure ridotte su griglia log (nome, f, z, parametri, note, visibilità) |
| `last` | ultima misura a piena risoluzione (workbench) |
| `vas` | seconda misura per Vas (scatola o massa aggiunta) |
| `rnb_ref`, `rnb_log` | riferimento e storico del Rub & Buzz |

Chiavi dei widget (addendum Streamlit §1): azioni con prefisso `btn_`, widget transitori delle
memorie con prefisso `temp_mem_`. Nessuna chiave di widget coincide con una chiave di stato.

## Invarianti

- Un risultato di `params.free_air` con chiave `errore` viene mostrato e non usato: niente Vas,
  niente riferimento Rub & Buzz, niente seconda misura Vas.
- Gli avvisi `_avvisi` (es. f2 ricavata per media geometrica) sono mostrati sopra i parametri.
- Calibrazione e componenti si misurano a `CAL_LEVEL` (−3 dBFS): con lo sweep il canale di
  riferimento resta sotto ~0,6 FS.
- I moduli del backend vengono ricaricati a ogni esecuzione (`importlib.reload`), in ordine
  `hardware, dsp, calibration, params, export`.

## Verifica

- Automatica: `UI.test_app_renders` in `tests/test_dats.py` (AppTest headless, 7 schede, nessuna eccezione).
- Manuale con hardware: `streamlit run app.py`, calibrazione → "Verifica" sul 1 kΩ (≈1000 Ω),
  free-air su un driver.
