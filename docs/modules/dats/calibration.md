# dats/calibration.py — calibrazione Open/Short/Load

Sorgenti: `dats/calibration.py` · dipende da `dsp.frac_octave_smooth`

## Modello

```
x = r / r_aperto
Z = Rs(f) · x / (1 − x) − Z_puntali(f)
```

- `r_aperto`: rapporto con puntali aperti (sbilanciamento dei canali e capacità d'ingresso).
- `Rs(f)`: dalla misura sul resistore di calibrazione (1 kΩ frontale), risolta in forma chiusa
  includendo i puntali: `Rs = Rcal·a / (1 − a·xs/(1 − xs))`, con `a = (1 − xl)/xl`.
- `Z_puntali(f)`: dalla misura in corto, `Rs · xs / (1 − xs)`.

Si salvano i **rapporti grezzi** (smoothing 1/6 ottava, griglia log fissa di 800 punti 1 Hz–22 kHz),
non Rs e Z_puntali: così l'ordine delle tre misure è libero e i valori derivati restano coerenti.

## API

- `Calibration.set_open / set_load(f, ratio, r_cal_ohm) / set_short / reset`
- `r_open_at(f)`, `rs_at(f)`, `z_lead_at(f)`, `apply(f, ratio, subtract_leads=True)`
- `summary()`: stato, Rs a 1 kHz, resistenza dei puntali a 100 Hz.
- `save(path)`, `Calibration.load(path)`: JSON in `%APPDATA%/dats_streamlit/calibration.json`
  (`$XDG_CONFIG_HOME` o `~/.config` altrove). Un file mancante o corrotto restituisce una
  calibrazione vuota.

## Default senza calibrazione

`Rs = 93,9 Ω`, `r_aperto = 0,9972` (misurati sull'unità di sviluppo), puntali 0 Ω: precisione ~10%
su altre unità, come il DATS originale non calibrato.

## Valori di riferimento (unità di sviluppo)

Rs ≈ 93,96 Ω, puntali ≈ 0,687 Ω (il software originale salvava 0,690 Ω in `DATS.ini`).

## Verifica

- Automatica: `Calib.test_open_short_load_round_trip` (Rs, r_aperto e puntali complessi e dipendenti
  da f: errore < 0,2% su un driver sintetico), `Calib.test_serialization`.
- Manuale: dopo la calibrazione, "Verifica" sul 1 kΩ ≈ 1000,0 Ω e sul corto ≈ 0,00 Ω.
