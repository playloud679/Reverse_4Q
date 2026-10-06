# dats/hardware.py — accesso audio al DATS V3

Sorgenti: `dats/hardware.py` · dipendenza: `sounddevice` (PortAudio)

## Hardware

Il DATS V3 è una scheda audio USB stereo (TI PCM2900C, VID 08BB / PID 29C0). Schema ricavato
misurando carichi noti (aperto, corto, 1 kΩ interno):

```
OUT sinistro ──┬──[ Rs ≈ 94 Ω ]──┬── puntale rosso ── DUT ── puntale nero ── GND
           IN destro         IN sinistro
        (riferimento)      (tensione sul DUT)
```

L'uscita destra non ha effetto sul circuito.

## API

- `list_devices()` → `[(index, etichetta, max_in, max_out, host_api)]`.
- `find_dats_devices()` → `(in, out)` sulla stessa host API, oppure `(None, None)`. Riconosce i nomi
  contenenti "USB AUDIO", "USB Audio CODEC" o "PCM2900". Ordine di preferenza: Windows DirectSound,
  MME, WASAPI, WDM-KS; macOS Core Audio; Linux ALSA, JACK, PulseAudio.
- `playrec(out, fs, dev_in, dev_out)` → registrazione `n × 2` in float. Solleva `RuntimeError`
  **prima** di aprire lo stream se un dispositivo manca o non è stereo (addendum audio §3.1).

## Note

- Su Windows WASAPI condiviso apre il DATS a 48 kHz in uscita e 44,1 kHz in ingresso: per questo si
  preferisce DirectSound/MME, che ricampionano. Il rapporto fra i due ingressi non ne risente.
- Gli errori di PortAudio risalgono al chiamante; `app.py` li mostra all'utente.

## Verifica

Manuale (richiede il DATS): `find_dats_devices()` restituisce una coppia valida;
`playrec(..., dev_out=None)` solleva `RuntimeError`.
