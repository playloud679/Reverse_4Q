"""Esportazione nei formati DATS (.zma, .txt) e progetto JSON.

Documentazione: docs/modules/dats/export.md
"""
from __future__ import annotations

import json

import numpy as np


def to_zma(f, z) -> str:
    lines = [f"{fi:.4f} {abs(zi):.5f} {np.degrees(np.angle(zi)):.3f}" for fi, zi in zip(f, z)]
    return "\n".join(lines) + "\n"


def from_zma(text: str):
    rows = []
    for ln in text.splitlines():
        parts = ln.replace(",", " ").replace(";", " ").split()
        try:
            rows.append([float(p) for p in parts[:3]])
        except ValueError:
            continue
    a = np.array([r for r in rows if len(r) == 3])
    return a[:, 0], a[:, 1] * np.exp(1j * np.radians(a[:, 2]))


def params_txt(name: str, notes: str, params: dict) -> str:
    out = [f"DATS (Streamlit) — {name}", notes, ""]
    for k, v in params.items():
        if isinstance(v, dict) or k.startswith("_"):
            continue
        out.append(f"{k:24s} {v:.6g}" if isinstance(v, (int, float)) else f"{k:24s} {v}")
    return "\n".join(out) + "\n"


def project_json(memories: list[dict]) -> str:
    enc = []
    for m in memories:
        d = dict(m)
        d["f"] = np.asarray(m["f"]).tolist()
        d["z"] = [np.asarray(m["z"]).real.tolist(), np.asarray(m["z"]).imag.tolist()]
        enc.append(d)
    return json.dumps({"version": 1, "memories": enc}, default=float)


def project_load(text: str) -> list[dict]:
    d = json.loads(text)
    mems = []
    for m in d["memories"]:
        m["f"] = np.array(m["f"])
        m["z"] = np.array(m["z"][0]) + 1j * np.array(m["z"][1])
        mems.append(m)
    return mems
