"""Segnali di test periodici (sweep, multitono) e misura del rapporto fra i due ingressi.

Come il software originale, si usa un segnale periodico a larga banda e la FFT
su un numero intero di periodi (DATS V3: periodo 128k campioni a 44.1 kHz).
Il rapporto IN_L / IN_R non dipende dalla latenza né dal volume di uscita.

Documentazione: docs/modules/dats/dsp.md
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import hardware

QUALITY = {  # nome: (periodo FFT, medie)
    "Veloce (0.67 Hz, ~3 s)": (2**16, 1),
    "Normale (0.34 Hz, ~6 s)": (2**17, 1),
    "Alta (0.34 Hz, 3 medie, ~12 s)": (2**17, 3),
}


@dataclass
class RawMeasurement:
    f: np.ndarray            # frequenze dei bin eccitati
    ratio: np.ndarray        # IN_dut / IN_ref (complesso)
    noise: np.ndarray        # dev. std. stimata del rapporto (nan se 1 media)
    fs: int
    n_fft: int
    level_dbfs: float
    peak_in: float
    meta: dict = field(default_factory=dict)

    @property
    def clipped(self) -> bool:
        return self.peak_in > 0.98


EXCITATIONS = {
    "Sweep (come DATS)": "sweep",
    "Multitono (livello basso sul driver)": "multitone",
}


def excitation(n: int, fs: int, fmin: float = 1.0, fmax: float = 20000.0, seed: int = 1,
               kind: str = "sweep"):
    """Segnale periodico a spettro 'rosa' (|X| ∝ 1/√f), picco normalizzato a 1.

    - "sweep": sweep logaritmico periodico sintetizzato in frequenza. Ogni frequenza
      riceve tutta la tensione per un istante, come lo sweep del DATS originale:
      a parità di picco pilota il driver molto più forte del multitono.
    - "multitone": fasi casuali, energia distribuita su tutte le frequenze insieme.
    """
    f = np.fft.rfftfreq(n, 1 / fs)
    band = (f >= fmin) & (f <= min(fmax, 0.95 * fs / 2))
    mag = 1 / np.sqrt(np.maximum(f[band], 10.0))
    X = np.zeros(len(f), complex)
    if kind == "sweep":
        f1, f2 = f[band][0], f[band][-1]
        period = n / fs
        tau = 0.9 * period * np.log(f[band] / f1) / np.log(f2 / f1)   # ritardo di gruppo
        phase = -2 * np.pi * np.cumsum(tau) * (fs / n)
        X[band] = mag * np.exp(1j * phase)
        x = np.fft.irfft(X, n)
        x = np.roll(x, int(0.05 * n))   # lascia il "ritorno" del periodo fuori dall'inizio
        return x / np.max(np.abs(x)), band
    rng = np.random.default_rng(seed)
    X[band] = np.exp(2j * np.pi * rng.random(band.sum())) * mag
    x = np.fft.irfft(X, n)
    # qualche iterazione di clipping per ridurre il fattore di cresta
    for _ in range(12):
        lim = 0.75 * np.max(np.abs(x))
        y = np.clip(x, -lim, lim)
        Y = np.fft.rfft(y)
        X2 = np.zeros_like(X)
        X2[band] = np.abs(X[band]) * np.exp(1j * np.angle(Y[band]))
        x = np.fft.irfft(X2, n)
    x /= np.max(np.abs(x))
    return x, band


def measure(dev_in: int, dev_out: int, fs: int = 44100, n_fft: int = 2**16, n_avg: int = 1,
            level_dbfs: float = -3.0, fmin: float = 1.0, fmax: float = 20000.0,
            dut_ch: int = 0, ref_ch: int = 1, out_ch: int = 0,
            kind: str = "sweep") -> RawMeasurement:
    x, band = excitation(n_fft, fs, fmin, fmax, kind=kind)
    amp = 10 ** (level_dbfs / 20)
    # in testa 1 periodo intero (≥1,5 s) di assestamento, in coda 0,5 s per la latenza:
    # i blocchi analizzati non toccano mai i bordi dello stream
    pad = int(0.5 * fs)
    total = (1 + n_avg) * n_fft + pad
    sig = np.tile(x, 2 + n_avg)[:total] * amp
    ramp = int(0.02 * fs)
    sig[:ramp] *= np.linspace(0, 1, ramp)
    sig[-ramp:] *= np.linspace(1, 0, ramp)
    out = np.zeros((total, 2))
    out[:, out_ch] = sig
    rec = hardware.playrec(out, fs, dev_in, dev_out)
    peak = float(np.max(np.abs(rec)))
    blocks = rec[n_fft:(1 + n_avg) * n_fft].reshape(n_avg, n_fft, 2)
    Y = np.fft.rfft(blocks, axis=1)[:, band, :]
    ratios = Y[:, :, dut_ch] / Y[:, :, ref_ch]
    Ym = Y.mean(axis=0)
    ratio = Ym[:, dut_ch] / Ym[:, ref_ch]
    noise = ratios.std(axis=0) / np.sqrt(n_avg) if n_avg > 1 else np.full(len(ratio), np.nan)
    f = np.fft.rfftfreq(n_fft, 1 / fs)[band]
    return RawMeasurement(f, ratio, noise, fs, n_fft, level_dbfs, peak)


def frac_octave_smooth(f: np.ndarray, y: np.ndarray, frac: float = 24.0) -> np.ndarray:
    """Smoothing a frazione d'ottava (media mobile su finestra ±1/(2·frac) ottave)."""
    if frac <= 0:
        return y.copy()
    lf = np.log2(f)
    half = 0.5 / frac
    lo = np.searchsorted(lf, lf - half, side="left")
    hi = np.searchsorted(lf, lf + half, side="right")
    c = np.concatenate([[0], np.cumsum(y)])
    return (c[hi] - c[lo]) / (hi - lo)


def log_resample(f: np.ndarray, z: np.ndarray, n: int = 1500, fmin: float | None = None,
                 fmax: float | None = None):
    """Riduce i dati su una griglia logaritmica (media complessa per intervallo)."""
    fmin = fmin or f[0]
    fmax = fmax or f[-1]
    edges = np.geomspace(fmin, fmax, n + 1)
    idx = np.searchsorted(edges, f) - 1
    ok = (idx >= 0) & (idx < n)
    cnt = np.bincount(idx[ok], minlength=n)
    zr = np.bincount(idx[ok], weights=z[ok].real, minlength=n)
    zi = np.bincount(idx[ok], weights=z[ok].imag, minlength=n)
    fs_ = np.bincount(idx[ok], weights=f[ok], minlength=n)
    m = cnt > 0
    return fs_[m] / cnt[m], (zr[m] + 1j * zi[m]) / cnt[m]


def generate(kind: str, fs: int, seconds: float, freq: float = 1000.0, level_dbfs: float = -10.0,
             f1: float = 20.0, f2: float = 20000.0) -> np.ndarray:
    """Generatore di segnali (come il generatore DATS)."""
    n = int(fs * seconds)
    t = np.arange(n) / fs
    a = 10 ** (level_dbfs / 20)
    ph = 2 * np.pi * freq * t
    if kind == "Sinusoide":
        y = np.sin(ph)
    elif kind == "Quadra":
        y = np.sign(np.sin(ph))
    elif kind == "Triangolare":
        y = 2 / np.pi * np.arcsin(np.sin(ph))
    elif kind == "Dente di sega":
        y = 2 * ((freq * t) % 1.0) - 1
    elif kind == "Impulsi":
        y = np.zeros(n)
        y[:: max(1, int(fs / freq))] = 1.0
    elif kind == "Rumore bianco":
        y = np.random.default_rng().uniform(-1, 1, n)
    elif kind == "Rumore rosa":
        w = np.fft.rfft(np.random.default_rng().standard_normal(n))
        ff = np.fft.rfftfreq(n, 1 / fs)
        w[1:] /= np.sqrt(ff[1:])
        w[0] = 0
        y = np.fft.irfft(w, n)
        y /= np.max(np.abs(y))
    elif kind == "Sweep logaritmico":
        k = np.log(f2 / f1)
        y = np.sin(2 * np.pi * f1 * seconds / k * (np.exp(t / seconds * k) - 1))
    else:
        raise ValueError(kind)
    return a * y
