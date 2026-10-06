# dats/params.py — parametri

Sorgenti: `dats/params.py` · dipende da `dsp.frac_octave_smooth` · solo NumPy (niente SciPy)

Formule dalle Tech Note 1–3 della guida DATS (J. L. Murphy). ρ = 1,18 kg/m³, c = 345 m/s.

## Free-air: `free_air(f, z, re_override, fmin, fmax, le_freqs)`

1. **Risonanza** (`find_resonance`): massimi locali di |Z| (smoothing 1/48 ott.) con prominenza
   ≥ 2% e |fase| < 25°; si sceglie il più alto. Mai `argmax` globale: la salita induttiva in alta
   frequenza può superare Zmax (addendum audio §2.1). Rifinitura sub-bin con polinomio di 4° grado
   in log f su ±4% (DATS usa una spline cubica).
2. **Re**: fit complesso Levenberg–Marquardt di `Re + Res/(1 + jQms(f/fs − fs/f)) + jωLe` su
   [fs/8, 4·fs]. Sovrascrivibile con `re_override`.
3. **Metodo classico**: `r0 = Zmax/Re`, soglia `Re·√r0`; f1 scendendo dal picco, f2 salendo.
   Se uno dei due manca: `f2 = fs²/f1` o `f1 = fs²/f2`, con avviso in `_avvisi`.
   `Qms = fs·√r0/(f2 − f1)`, `Qes = Qms/(r0 − 1)`, `Qts = Qms·Qes/(Qms + Qes)`.
4. **Le** a 1 e 10 kHz e **Wright** (7/14 kHz) calcolati sull'impedenza della bobina, cioè dopo aver
   tolto la parte mozionale stimata dal fit. Scelta di progetto (priorità 2 sullo standard): sopra Fs
   la parte mozionale è capacitiva e su driver con Fs alta rende Le a 1 kHz negativo.

Restituisce un dizionario con `fs, Re, Zmax, Qms, Qes, Qts, f1, f2, fs_geom, Rnom, fit, _avvisi,
Le@1k, Le@10k` ed eventualmente `Kr, Xr, Ki, Xi`; in caso di errore solo `{"errore": testo}`:

- nessuna risonanza;
- `Zmax > Re > 0` violato;
- f1 e f2 entrambi non trovati, oppure `0 < f1 < fs < f2` violato.

## Wright: `wright(f, z_bobina, re, f1=7000, f2=14000)`

`Z = Re + Kr·ω^Xr + j·Ki·ω^Xi`. Restituisce `{}` se i dati non arrivano a 14,3 kHz o se una delle
parti reale (oltre Re) o immaginaria non è positiva: niente NaN.

## Vas: `derived(p, sd_m2, metodo, **kw)`

| Metodo | Ingressi | Formula |
|---|---|---|
| Scatola di test | `vb_l, fct, qect` | `Vas = Vt·(fct·Qect/(fs·Qes) − 1)` |
| Massa aggiunta | `ma_g, fsa` | `Mms = Ma/((fs/fsa)² − 1)`; avviso se lo spostamento di Fs non è 25–50% |
| SPL specificato | `spl` (1 W/1 m) | `Vas[ft³] = 10^((SPL − 112,1)/10)·Qes/(2,7e-8·fs³)` |
| Mmd specificata | `mmd_g` | `Mms = Mmd + 16ρa³/3` (carico d'aria su due facce) |

Poi `Cms, Mms, BL = √(2π·fs·Mms·Re/Qes), Rms, η0 = 4π²/c³·fs³·Vas/Qes, SPL 1 W e 2,83 V`.
η0 SI coincide con la formula DATS in piedi cubi entro l'1%.

## Componenti

- `resistor`: mediana di Re(Z) fra 20 Hz e 2 kHz.
- `inductor`: mediana di Im(Z)/ω dove 1 Ω ≤ |Z| ≤ 2 kΩ; DCR = mediana di Re(Z) a 10–50 Hz.
- `capacitor`: mediana di −1/(ω·Im Z) nella stessa zona; ESR, DF, Q, δ a 120 Hz, 1 kHz, 10 kHz.
- `within_geometric(v, ref, tol%)`: tolleranza Rub & Buzz di DATS (100% = fattore 2 nei due versi).

## Verifica

Automatica in `tests/test_dats.py`: `FreeAir.*` (driver sintetico, salita induttiva, f2 mascherata,
errore senza risonanza, Wright), `Derived.*` (relazioni Mmd, accordo fra i metodi), `Components.*`,
`Export.test_original_dats_export_regression` (Fs 132,9 ± 1 Hz e Qts 0,567 ± 0,02 sull'export DATS).
