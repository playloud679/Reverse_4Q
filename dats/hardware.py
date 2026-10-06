"""Accesso audio al DATS V3 (PortAudio via sounddevice, multipiattaforma).

Il DATS V3 è una scheda audio USB (TI PCM2900C, VID 08BB / PID 29C0).
Schema ricavato per retro-ingegneria:

    OUT sinistro ──┬──[ Rs ≈ 94 Ω ]──┬── puntale rosso ── DUT ── puntale nero ── GND
                   │                 │
               IN destro         IN sinistro
            (riferimento)      (tensione sul DUT)

L'uscita destra non è usata.
"""
from __future__ import annotations

import platform

import numpy as np
import sounddevice as sd

DATS_NAME_HINTS = ("USB AUDIO", "USB Audio CODEC", "PCM2900")

# Host API preferite per sistema (WASAPI condiviso usa 48k in uscita e 44.1k in ingresso
# sul DATS, quindi su Windows si preferisce DirectSound/MME che ricampionano).
_PREFERRED_APIS = {
    "Windows": ("Windows DirectSound", "MME", "Windows WASAPI", "Windows WDM-KS"),
    "Darwin": ("Core Audio",),
    "Linux": ("ALSA", "JACK Audio Connection Kit", "PulseAudio"),
}


def list_devices():
    """Restituisce [(index, label, max_in, max_out, hostapi_name)]."""
    out = []
    apis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        api = apis[d["hostapi"]]["name"]
        out.append((i, f"[{i}] {d['name']} — {api}", d["max_input_channels"], d["max_output_channels"], api))
    return out


def _is_dats(name: str) -> bool:
    n = name.upper()
    return any(h.upper() in n for h in DATS_NAME_HINTS)


def find_dats_devices():
    """Trova (input_index, output_index) del DATS sulla stessa host API, o (None, None)."""
    devs = sd.query_devices()
    apis = sd.query_hostapis()
    prefs = _PREFERRED_APIS.get(platform.system(), ())
    by_api: dict[str, dict[str, int]] = {}
    for i, d in enumerate(devs):
        if not _is_dats(d["name"]):
            continue
        api = apis[d["hostapi"]]["name"]
        slot = by_api.setdefault(api, {})
        if d["max_input_channels"] >= 2 and "in" not in slot:
            slot["in"] = i
        if d["max_output_channels"] >= 2 and "out" not in slot:
            slot["out"] = i
    complete = {a: s for a, s in by_api.items() if "in" in s and "out" in s}
    for api in prefs:
        if api in complete:
            return complete[api]["in"], complete[api]["out"]
    if complete:
        s = next(iter(complete.values()))
        return s["in"], s["out"]
    return None, None


def playrec(out: np.ndarray, fs: int, dev_in: int, dev_out: int) -> np.ndarray:
    """Riproduce `out` (n x 2) e registra 2 canali in contemporanea."""
    rec = sd.playrec(out.astype(np.float32), samplerate=fs, channels=2,
                     device=(dev_in, dev_out), dtype="float32", blocking=True)
    return rec.astype(float)
