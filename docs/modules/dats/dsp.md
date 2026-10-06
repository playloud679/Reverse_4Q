# dats/dsp.py — segnali di test e misura

Sorgenti: `dats/dsp.py` · dipende da `hardware`

## API

- `QUALITY`: nome → (periodo FFT, numero di medie). 64k = 0,67 Hz/bin; 128k = 0,34 Hz/bin a 44,1 kHz.
- `EXCITATIONS`: etichetta UI → `"sweep"` | `"multitone"`.
- `excitation(n, fs, fmin, fmax, seed, kind)` → `(x, band)`. Segnale periodico di `n` campioni,
  picco 1, spettro |X| ∝ 1/√max(f, 10 Hz), energia solo nei bin di `band`.
  - `sweep`: sweep logaritmico sintetizzato in frequenza (ritardo di gruppo log su 90% del periodo).
    Pilota ogni frequenza con tutta la tensione per un istante, come il DATS originale.
  - `multitone`: fasi casuali con riduzione del fattore di cresta per clipping iterativo.
- `measure(dev_in, dev_out, fs, n_fft, n_avg, level_dbfs, fmin, fmax, dut_ch, ref_ch, out_ch, kind)`
  → `RawMeasurement(f, ratio, noise, fs, n_fft, level_dbfs, peak_in)`. `ratio = IN_dut / IN_ref`
  sui bin eccitati, media complessa su `n_avg` periodi; `noise` solo se `n_avg > 1`.
- `frac_octave_smooth(f, y, frac)`: media mobile su ±1/(2·frac) ottave (somme cumulative, O(n)).
- `log_resample(f, z, n)`: media complessa su `n` intervalli logaritmici; scarta gli intervalli vuoti.
- `generate(kind, fs, seconds, freq, level_dbfs, f1, f2)`: generatore di forme d'onda.

## Invarianti e scelte

- Stream = 1 periodo di assestamento (≥1,5 s) + `n_avg` periodi analizzati + 0,5 s di coda
  (addendum audio §3.2). Rampe di 20 ms solo ai bordi, mai nei blocchi analizzati.
- Il rapporto fra i due ingressi elimina latenza, volume di uscita e risposta dei convertitori.
- Con lo sweep a −3 dBFS il picco sul canale di riferimento è ~0,6 FS. Con il multitono il passa-alto
  d'ingresso alza il fattore di cresta: a −1 dBFS il riferimento satura (`RawMeasurement.clipped`).
- Il driver di prova è non lineare: a parità di picco, il multitono dà Fs più alta del 15% rispetto
  allo sweep. Usare lo sweep per confrontare con il DATS originale.

## Verifica

- Automatica: `Signals.*` in `tests/test_dats.py` (periodicità, banda, picco, fattore di cresta < 2,5;
  ricampionamento log).
- Manuale: puntali in corto → |Z| < 0,02 Ω dopo calibrazione; resistore 1 kΩ → 1000 ± 1 Ω.
