# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [0.2.0] — 2026-10-06

### Aggiunto
- Segnale di test **sweep logaritmico periodico** (predefinito), che pilota il driver come il DATS
  originale. Il multitono resta selezionabile da "Segnale di test" nella barra laterale.
- Versione mostrata nella barra laterale.
- README con installazione, confronto con il software originale e note di retro-ingegneria;
  questo CHANGELOG; `.gitignore`.

### Modificato
- Livello predefinito −3 dBFS (prima −6); calibrazione e componenti misurati a −3 dBFS.
- Multitono con meno enfasi sotto i 10 Hz, per ridurre il fattore di cresta dopo il filtro
  passa-alto d'ingresso.

### Corretto
- Fs e Q ora concordano con il DATS originale (Fs 131,2 contro 132,9 Hz, scarto mediano su |Z| 0,5%).
  Con il multitono la risonanza riceveva poca tensione e Fs risultava più alta del 15%.

## [0.1.0] — 2026-10-05

### Aggiunto
- Prima versione: rilevamento automatico del DATS V3, misura d'impedenza a multitono, calibrazione
  aperto / 1 kΩ / corto, parametri T/S, Vas (4 metodi), Wright, R/L/C, linearità, rub & buzz,
  memorie, export `.zma`/`.txt`, generatore e oscilloscopio.
- Ripetizione automatica a livello più basso se l'ingresso satura.
- Nessuna dipendenza da SciPy (ricerca picchi, rifinitura di Fs e fit Levenberg–Marquardt in NumPy).
