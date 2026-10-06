"""Calibrazione: aperto (opzionale), 1 kΩ di riferimento e corto dei puntali.

Modello (verificato sull'hardware):
    r  = IN_dut / IN_ref
    x  = r / r_open                       (r_open = rapporto a puntali aperti)
    Z  = Rs · x / (1 − x) − Z_puntali

Rs (resistenza serie interna, ~94 Ω) si ricava dalla misura sul 1 kΩ frontale,
Z_puntali dal cortocircuito. Tutte le grandezze sono complesse e dipendenti dalla
frequenza, quindi il metodo equivale a una calibrazione Open/Short/Load.

Documentazione: docs/modules/dats/calibration.md
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .dsp import frac_octave_smooth

DEFAULT_RS = 93.9          # Ω, misurato su questa unità; usato prima della calibrazione
DEFAULT_R_OPEN = 0.9972
CAL_SMOOTH_OCT = 6.0       # le curve di calibrazione sono regolari: smoothing a 1/6 ott.


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    p = Path(base) / "dats_streamlit"
    p.mkdir(parents=True, exist_ok=True)
    return p


CAL_FILE = _config_dir() / "calibration.json"


def _grid():
    return np.geomspace(1.0, 22000.0, 800)


def _to_grid(f, r):
    """Smoothing e ricampionamento su griglia log fissa (complesso)."""
    sm = frac_octave_smooth(f, r.real, CAL_SMOOTH_OCT) + 1j * frac_octave_smooth(f, r.imag, CAL_SMOOTH_OCT)
    g = _grid()
    lf = np.log(f)
    return np.interp(np.log(g), lf, sm.real) + 1j * np.interp(np.log(g), lf, sm.imag)


@dataclass
class Calibration:
    r_open: np.ndarray | None = None
    r_load: np.ndarray | None = None
    r_short: np.ndarray | None = None
    r_cal_ohm: float = 1000.0
    info: dict = field(default_factory=dict)

    # ---- acquisizione -------------------------------------------------
    def set_open(self, f, ratio):
        self.r_open = _to_grid(f, ratio)

    def set_load(self, f, ratio, r_cal_ohm=1000.0):
        self.r_load = _to_grid(f, ratio)
        self.r_cal_ohm = float(r_cal_ohm)

    def set_short(self, f, ratio):
        self.r_short = _to_grid(f, ratio)

    def reset(self):
        self.r_open = self.r_load = self.r_short = None

    # ---- grandezze derivate ------------------------------------------
    def _interp(self, arr, f):
        g = np.log(_grid())
        lf = np.log(np.clip(f, 1.0, 22000.0))
        return np.interp(lf, g, arr.real) + 1j * np.interp(lf, g, arr.imag)

    def r_open_at(self, f):
        return self._interp(self.r_open, f) if self.r_open is not None else np.full(len(f), DEFAULT_R_OPEN, complex)

    def rs_at(self, f):
        """Resistenza serie interna complessa Rs(f)."""
        if self.r_load is None:
            return np.full(len(f), DEFAULT_RS, complex)
        ro = self.r_open_at(f)
        xl = self._interp(self.r_load, f) / ro
        a = (1 - xl) / xl
        if self.r_short is not None:
            xs = self._interp(self.r_short, f) / ro
            # (Rcal + Zlead)·a = Rs, con Zlead = Rs·xs/(1−xs)
            return self.r_cal_ohm * a / (1 - a * xs / (1 - xs))
        return self.r_cal_ohm * a

    def z_lead_at(self, f):
        if self.r_short is None:
            return np.zeros(len(f), complex)
        xs = self._interp(self.r_short, f) / self.r_open_at(f)
        return self.rs_at(f) * xs / (1 - xs)

    def apply(self, f, ratio, subtract_leads=True):
        x = ratio / self.r_open_at(f)
        z = self.rs_at(f) * x / (1 - x)
        if subtract_leads:
            z = z - self.z_lead_at(f)
        return z

    def summary(self):
        f1k = np.array([1000.0])
        return {
            "aperto": self.r_open is not None,
            "1kΩ": self.r_load is not None,
            "corto": self.r_short is not None,
            "Rs @1kHz [Ω]": float(self.rs_at(f1k)[0].real),
            "Resistenza puntali [Ω]": float(self.z_lead_at(np.array([100.0]))[0].real),
        }

    # ---- persistenza --------------------------------------------------
    def to_dict(self):
        enc = lambda a: None if a is None else [a.real.tolist(), a.imag.tolist()]
        return {"version": 1, "r_open": enc(self.r_open), "r_load": enc(self.r_load),
                "r_short": enc(self.r_short), "r_cal_ohm": self.r_cal_ohm, "info": self.info}

    @classmethod
    def from_dict(cls, d):
        dec = lambda v: None if v is None else np.array(v[0]) + 1j * np.array(v[1])
        return cls(dec(d.get("r_open")), dec(d.get("r_load")), dec(d.get("r_short")),
                   d.get("r_cal_ohm", 1000.0), d.get("info", {}))

    def save(self, path: Path = CAL_FILE):
        Path(path).write_text(json.dumps(self.to_dict()))

    @classmethod
    def load(cls, path: Path = CAL_FILE):
        try:
            return cls.from_dict(json.loads(Path(path).read_text()))
        except (OSError, ValueError, KeyError):
            return cls()
