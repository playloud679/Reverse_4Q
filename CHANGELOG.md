# Changelog

Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [0.2.1] — 2026-10-06

Adozione di GOLDEN_STD 1.5.0 (`playloud679/dev_standards` @ `607da03`) con gli addenda Audio DSP
e Streamlit.

### Corretto
- **Parametri**: se f2 è mascherata dall'induttanza (o f1 dal limite in bassa) si ricava per media
  geometrica `f2 = Fs²/f1`, con avviso nell'interfaccia; prima Qms veniva preso dal fit senza dirlo.
- **Parametri**: errori espliciti se `Zmax > Re > 0` o `0 < f1 < Fs < f2` non sono rispettati.
- **Parametri**: `wright()` non produce più NaN quando le parti reale o immaginaria non sono positive.
- **Interfaccia**: una seconda misura Vas o un riferimento Rub & Buzz senza risonanza mostra un
  errore invece di andare in crash (`KeyError`).
- **Hardware**: `playrec` verifica che ingresso e uscita esistano e siano stereo prima di aprire lo stream.

### Modificato
- **Misura**: coda di latenza portata da 0,3 a 0,5 s.
- **Parametri**: η0 calcolato con la formula SI `4π²/c³·fs³·Vas/Qes` (identica a quella DATS in ft³).
- **Interfaccia**: chiavi dei widget separate (`btn_*` per le azioni, `temp_mem_*` per le memorie);
  moduli del backend ricaricati a ogni esecuzione.

### Documentazione e test
- Aggiunti `AGENTS.md`, `VERSION`, `GOLDEN_STD.md`, `addenda/`, `docs/INDEX.md` e un documento per
  ogni modulo in `docs/modules/`; docstring dei moduli con il rimando al documento.
- Aggiunta `tests/test_dats.py` (unittest, offline): driver sintetico, salita induttiva, f2 mascherata,
  Wright, metodi Vas, R/L/C, calibrazione Open/Short/Load, segnali, export, regressione sull'export
  del DATS originale, AppTest headless.

### Validazione
- `python -m unittest discover -s tests -v`: **16 test, 16 passati** (anche con
  `-W error::RuntimeWarning`).
- `python -m py_compile app.py dats/*.py`: ok.
- Misura reale con il DATS (driver di prova, sweep −3 dBFS): Fs 135,1 Hz, Qts 0,562, nessun avviso
  (DATS originale: 132,9 Hz, 0,567). `playrec` senza uscita solleva l'errore previsto.
- Non verificato: macOS e Linux (nessuna macchina disponibile).

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
