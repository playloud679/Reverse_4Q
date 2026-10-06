# dats/export.py — export e import

Sorgenti: `dats/export.py` · solo NumPy e libreria standard

## API

- `to_zma(f, z)`: righe `frequenza |Z| fase°`.
- `from_zma(text)` → `(f, z)`: accetta separatori spazio, tab, virgola o punto e virgola; ignora le
  righe non numeriche, quindi legge anche l'export `.txt` del DATS originale (intestazione con `*`).
- `params_txt(nome, note, params)`: parametri in testo; salta dizionari annidati e chiavi `_*`.
- `project_json(memorie)` / `project_load(testo)`: progetto con tutte le memorie; i numeri complessi
  sono salvati come coppia `[reali, immaginari]`.

## Verifica

Automatica: `Export.test_zma_round_trip`, `Export.test_original_dats_export_regression`
(344 punti dall'export del DATS originale).
