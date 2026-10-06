# Reverse 4Q — DATS V3 in Streamlit

App Streamlit **multipiattaforma** (Windows, macOS, Linux) che usa l'hardware
**Dayton Audio DATS V3** per fare le stesse misure del software originale, che gira solo su Windows.

Versione attuale: **0.2.0** — vedi [CHANGELOG.md](CHANGELOG.md).

## Funzioni

| Scheda | Cosa fa |
|---|---|
| 📈 Impedenza / T-S | Grafico di modulo e fase (anche parte reale e immaginaria), Fs, Re, Zmax, Qms, Qes, Qts, Le a 1 e 10 kHz, parametri di Wright (Kr, Xr, Ki, Xi) a 7 e 14 kHz |
| | Vas con i 4 metodi DATS: scatola di test, massa aggiunta, SPL dichiarato, Mmd dichiarata → Mms, Cms, BL, Rms, η0, SPL 1 W e 2,83 V |
| 🧩 R · L · C | Resistori; induttori con DCR; condensatori con ESR, DF, Q e angolo di perdita a 120 Hz, 1 kHz, 10 kHz |
| 📊 Linearità | Parametri free-air a più livelli di pilotaggio |
| 🐝 Rub & Buzz | Confronto di Fs e Zmax a livello ridotto con un driver di riferimento (tolleranza geometrica come DATS) |
| 💾 Memorie | Sovrapposizione curve, note, progetto JSON, export `.zma`/`.txt`, import `.zma` o export DATS |
| 〰️ Generatore / Scope | Sinusoide, quadra, triangolare, dente di sega, impulsi, rumore rosa/bianco, sweep; forma d'onda e spettro |
| 🎯 Calibrazione | Puntali aperti → resistore 1 kΩ frontale → puntali in corto |

## Installazione

```bash
git clone https://github.com/playloud679/Reverse_4Q.git
cd Reverse_4Q
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

- Python 3.10 o superiore.
- Su Linux serve PortAudio: `sudo apt install libportaudio2`.
- Non serve SciPy: l'app usa solo NumPy (su Windows con Smart App Control le DLL di SciPy vengono bloccate).

## Uso

1. Collega il DATS alla USB e avvia l'app: il dispositivo viene selezionato in automatico
   (altrimenti scegli ingresso e uscita "USB AUDIO CODEC" nella barra laterale).
2. Alla prima volta esegui la **calibrazione** nella scheda 🎯, nell'ordine:
   puntali aperti, puntali sui terminali metallici 1 kΩ del frontale, puntali in corto.
3. Collega l'altoparlante (scollegato da amplificatori e da massa) e premi **▶ Parametri free-air**.

Impostazioni predefinite: segnale **Sweep (come DATS)** a **−3 dBFS**, che riproduce i risultati del
software originale.

## Confronto con il software originale

Stesso altoparlante, sweep a −3 dBFS, contro un export del DATS originale
(`Exported Impedance Data.txt`, 344 punti):

| | DATS originale | App |
|---|---|---|
| Fs | 132,9 Hz | 131,2 Hz |
| Zmax | 26,8 Ω | 27,7 Ω |
| Qms | 3,95 | 4,06 |
| Qes | 0,662 | 0,619 |
| Qts | 0,567 | 0,537 |
| Scarto su \|Z\| | — | 0,5% mediano |

Sul resistore di calibrazione l'app legge 1000,0 Ω; con i puntali in corto 0,005 Ω.
Il driver di prova è molto non lineare (Fs 171 Hz a −36 dBFS, 147 Hz a −4 dBFS con il multitono),
quindi per confrontare Fs e Q bisogna usare lo sweep e un livello simile.

## Come funziona l'hardware (retro-ingegneria)

Il DATS V3 è una scheda audio USB stereo (TI PCM2900C, VID 08BB / PID 29C0):

```
OUT sinistro ──┬──[ Rs ≈ 94 Ω ]──┬── puntale rosso ── DUT ── puntale nero ── GND
               │                 │
           IN destro         IN sinistro
        (riferimento)      (tensione sul DUT)
```

L'uscita destra non è usata.

- `r = IN_L / IN_R`: rapporto complesso per bin FFT, indipendente da latenza e volume
- `x = r / r_aperto`
- `Z = Rs · x / (1 − x) − Z_puntali`

`Rs(f)` si ricava dal resistore da 1 kΩ, `Z_puntali(f)` dal corto: equivale a una calibrazione
Open/Short/Load. La calibrazione è salvata in `%APPDATA%\dats_streamlit\calibration.json`
(`~/.config/dats_streamlit/` su macOS/Linux).

Il segnale di test è periodico (64k o 128k campioni a 44,1 kHz) e viene analizzato con la FFT su
un numero intero di periodi, come la FFT 128k di DATS V3. Le formule dei parametri sono quelle delle
Tech Note incluse nella guida DATS.

Il software originale salva la calibrazione dei puntali in `TestLeads.cal`: `int32` versione (= 3)
seguito da 262144 `complex128` (impedenza dei puntali per bin, FFT 2^18 a 44,1 kHz, solo bin pari
valorizzati).

## Struttura

```
app.py              interfaccia Streamlit
dats/hardware.py    rilevamento del DATS e I/O audio (sounddevice / PortAudio)
dats/dsp.py         segnali di test (sweep, multitono), misura, smoothing, generatore
dats/calibration.py calibrazione aperto / 1 kΩ / corto
dats/params.py      parametri T/S, Vas, Wright, R/L/C, rub & buzz
dats/export.py      .zma, .txt, progetto JSON
```

## Limiti

- I livelli sono in dBFS: senza un multimetro l'app non conosce i volt reali in uscita.
  Nello scope puoi inserire i volt di picco a 0 dBFS per leggere in volt.
- Sopra circa −1 dBFS il canale di riferimento può saturare: l'app ripete la misura 6 dB più in basso.
- Le a 1 kHz viene calcolato togliendo la parte mozionale della risonanza, quindi su driver con Fs
  alta può differire dal valore del software originale.

## Sicurezza

Non collegare mai i puntali a un altoparlante collegato a un amplificatore o a massa.
