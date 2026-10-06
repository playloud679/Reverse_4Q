"""Estrazione dei parametri, con le stesse formule documentate nella guida DATS
(Tech Note 1, 2, 3 di J. L. Murphy): T/S free-air, Vas (4 metodi), Wright, R/L/C.

Documentazione: docs/modules/dats/params.md
"""
from __future__ import annotations

import math

import numpy as np

from .dsp import frac_octave_smooth

RHO = 1.18     # kg/m³ (valori usati da DATS)
C_AIR = 345.0  # m/s
FT3_PER_L = 0.0353147


# ---------------------------------------------------------------- utilità
def _band(f, z, lo, hi):
    m = (f >= lo) & (f <= hi)
    return f[m], z[m]


def _value_at(f, z, f0, rel=0.03):
    """Valore mediano (complesso) in un intorno ±rel di f0."""
    m = (f >= f0 * (1 - rel)) & (f <= f0 * (1 + rel))
    if not m.any():
        return complex("nan")
    return complex(np.median(z[m].real), np.median(z[m].imag))


def _local_maxima(y, min_prominence):
    """Indici dei massimi locali con prominenza minima (sostituto di find_peaks)."""
    idx = np.where((y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:]))[0] + 1
    out = []
    for i in idx:
        left, right = y[:i].min(initial=y[i]), y[i + 1:].min(initial=y[i])
        # prominenza: altezza rispetto alla più alta delle due "valli" fino a un picco più alto
        lh = np.where(y[:i] > y[i])[0]
        rh = np.where(y[i + 1:] > y[i])[0]
        if len(lh):
            left = y[lh[-1]:i].min()
        if len(rh):
            right = y[i + 1:i + 1 + rh[0]].min()
        if y[i] - max(left, right) >= min_prominence:
            out.append(i)
    return out


def _levenberg_marquardt(resid, p0, lb, ub, iters=200):
    """LM minimale con Jacobiano numerico e vincoli a box (sostituto di least_squares)."""
    p = np.clip(np.asarray(p0, float), lb, ub)
    lam = 1e-3
    r = resid(p)
    cost = r @ r
    for _ in range(iters):
        J = np.empty((len(r), len(p)))
        for j in range(len(p)):
            h = 1e-6 * max(abs(p[j]), 1e-9)
            pj = p.copy(); pj[j] += h
            J[:, j] = (resid(pj) - r) / h
        A = J.T @ J
        g = J.T @ r
        while True:
            try:
                step = np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), -g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            pn = np.clip(p + step, lb, ub)
            rn = resid(pn)
            cn = rn @ rn
            if cn < cost:
                lam = max(lam / 3, 1e-9)
                break
            lam *= 4
            if lam > 1e9:
                return p
        done = abs(cost - cn) < 1e-12 * cost
        p, r, cost = pn, rn, cn
        if done:
            break
    return p


def nominal_impedance(re):
    for lo, hi, rn in [(0.8, 1.6, 1), (1.6, 3.2, 2), (3.2, 6.4, 4), (6.4, 12.8, 8),
                       (12.8, 25.6, 16), (25.6, 51.2, 32), (51.2, 102.4, 64)]:
        if lo <= re < hi:
            return rn
    return float("nan")


# ---------------------------------------------------------------- free air
def find_resonance(f, z, fmin=5.0, fmax=5000.0):
    """Frequenza di risonanza principale: massimo locale di |Z| con fase ≈ 0."""
    fb, zb = _band(f, z, fmin, fmax)
    mag = frac_octave_smooth(fb, np.abs(zb), 48)
    ph = np.degrees(np.angle(frac_octave_smooth(fb, zb.real, 48) + 1j * frac_octave_smooth(fb, zb.imag, 48)))
    pk = _local_maxima(mag, 0.02 * np.max(mag))
    if len(pk) == 0:
        return None
    good = [p for p in pk if abs(ph[p]) < 25]
    cand = good or list(pk)
    p = max(cand, key=lambda i: mag[i])
    # rifinitura sub-bin (DATS V3 usa una spline cubica): polinomio di 4° grado
    # in log(f) su ±4% attorno al picco, valutato su una griglia fine
    m_raw = frac_octave_smooth(fb, np.abs(zb), 96)
    sel = (fb >= fb[p] * 0.96) & (fb <= fb[p] * 1.04)
    if sel.sum() < 7:
        sel = np.zeros(len(fb), bool); sel[max(p - 4, 0):p + 5] = True
    lx = np.log(fb[sel])
    c = np.polyfit(lx - lx.mean(), m_raw[sel], min(4, sel.sum() - 1))
    ff = np.linspace(lx[0], lx[-1], 4000)
    v = np.polyval(c, ff - lx.mean())
    i = int(np.argmax(v))
    return float(np.exp(ff[i])), float(v[i])


def _motional_model(p, f):
    re, res, fs, qms, le = p
    w = 2 * np.pi * f
    return re + res / (1 + 1j * qms * (f / fs - fs / f)) + 1j * w * le


def fit_driver(f, z, fs0, zmax0, re0):
    """Fit complesso del modello Re + Zmot + jωLe intorno alla risonanza."""
    fb, zb = _band(f, z, max(fs0 / 8, f[0]), fs0 * 4)
    fb, zb = fb[::max(1, len(fb) // 3000)], zb[::max(1, len(zb) // 3000)]
    wts = 1 / np.sqrt(np.abs(zb))

    def resid(p):
        d = (_motional_model(p, fb) - zb) * wts
        return np.concatenate([d.real, d.imag])

    p0 = [re0, max(zmax0 - re0, 0.1), fs0, 5.0, 1e-4]
    lb = [0.01, 0.0, fs0 * 0.7, 0.3, 0]
    ub = [1e4, 1e5, fs0 * 1.3, 200, 0.1]
    x = _levenberg_marquardt(resid, p0, np.array(lb, float), np.array(ub, float))
    return dict(zip(["Re", "Res", "fs", "Qms", "Le"], x))


def free_air(f, z, re_override=None, fmin=5.0, fmax=5000.0, le_freqs=(1000.0, 10000.0)):
    res = find_resonance(f, z, fmin, fmax)
    if res is None:
        return {"errore": "Nessuna risonanza trovata"}
    fs, zmax = res
    re_lf = float(np.min(np.abs(_band(f, z, fmin, fs)[1]))) if (f < fs).any() else zmax / 5
    fit = fit_driver(f, z, fs, zmax, re_lf)
    re = float(re_override) if re_override else fit["Re"]

    # metodo classico Thiele/Small (TN1 DATS)
    r0 = zmax / re
    zx = re * math.sqrt(r0)
    fb, zb = _band(f, z, fs / 6, fs * 6)
    mag = frac_octave_smooth(fb, np.abs(zb), 96)
    below, above = fb < fs, fb > fs

    def cross(fx, mx):
        idx = np.where(np.diff(np.sign(mx - zx)) != 0)[0]
        return idx

    if not zmax > re > 0:
        return {"errore": f"Invariante violato: serve Zmax > Re > 0 (Zmax={zmax:.3g}, Re={re:.3g})"}

    # f1 scendendo dal picco verso DC, f2 salendo: ultimo/primo attraversamento di zx
    f1 = f2 = float("nan")
    ib = cross(fb[below], mag[below])
    if len(ib):
        i = ib[-1]
        x0, x1, y0, y1 = fb[below][i], fb[below][i + 1], mag[below][i], mag[below][i + 1]
        f1 = float(np.exp(np.log(x0) + (zx - y0) / (y1 - y0) * (np.log(x1) - np.log(x0))))
    ia = cross(fb[above], mag[above])
    if len(ia):
        i = ia[0]
        x0, x1, y0, y1 = fb[above][i], fb[above][i + 1], mag[above][i], mag[above][i + 1]
        f2 = float(np.exp(np.log(x0) + (zx - y0) / (y1 - y0) * (np.log(x1) - np.log(x0))))
    warnings = []
    # f2 mascherata dall'induttanza o f1 dal limite in bassa: media geometrica (addendum §2)
    if np.isfinite(f1) and not np.isfinite(f2):
        f2 = fs * fs / f1
        warnings.append("f2 non misurabile: ricavata come Fs²/f1")
    elif np.isfinite(f2) and not np.isfinite(f1):
        f1 = fs * fs / f2
        warnings.append("f1 non misurabile: ricavata come Fs²/f2")
    if not (np.isfinite(f1) and np.isfinite(f2)):
        return {"errore": "Punti a metà potenza f1 e f2 non trovati"}
    if not 0 < f1 < fs < f2:
        return {"errore": f"Invariante violato: serve 0 < f1 < Fs < f2 (f1={f1:.4g}, Fs={fs:.4g}, f2={f2:.4g})"}
    qms = fs * math.sqrt(r0) / (f2 - f1)
    qes = qms / (r0 - 1)
    qts = qms * qes / (qms + qes)

    out = {
        "fs": fs, "Re": re, "Zmax": zmax, "Qms": qms, "Qes": qes, "Qts": qts,
        "f1": f1, "f2": f2, "fs_geom": math.sqrt(f1 * f2), "Rnom": nominal_impedance(re),
        "fit": fit, "_avvisi": warnings,
    }
    # Le e Wright sull'impedenza della sola bobina: si toglie la parte mozionale
    # (sopra Fs è capacitiva e falserebbe Le a 1 kHz sui driver con Fs alta)
    zmot = fit["Res"] / (1 + 1j * fit["Qms"] * (f / fit["fs"] - fit["fs"] / f))
    zvc = z - zmot
    for fl in le_freqs:
        zl = _value_at(f, zvc, fl)
        out[f"Le@{fl/1000:g}k"] = zl.imag / (2 * math.pi * fl)
    out.update(wright(f, zvc, re))
    return out


def wright(f, z, re, f1=7000.0, f2=14000.0):
    """Parametri di Wright (Kr, Xr, Ki, Xi) a 7 e 14 kHz come DATS."""
    if f[-1] < f2 * 1.02:
        return {}
    z1, z2 = _value_at(f, z, f1), _value_at(f, z, f2)
    w1, w2 = 2 * math.pi * f1, 2 * math.pi * f2
    r1, r2 = z1.real - re, z2.real - re
    # il modello a potenze richiede parti reale (oltre Re) e immaginaria positive
    if not min(r1, r2, z1.imag, z2.imag) > 0:
        return {}
    xr = math.log(r2 / r1) / math.log(w2 / w1)
    xi = math.log(z2.imag / z1.imag) / math.log(w2 / w1)
    return {"Kr": r1 / w1 ** xr, "Xr": xr, "Ki": z1.imag / w1 ** xi, "Xi": xi}


# ---------------------------------------------------------------- Vas
def piston_area(diameter_cm):
    return math.pi * (diameter_cm / 200) ** 2


def air_load_mass(sd_m2):
    a = math.sqrt(sd_m2 / math.pi)
    return 16 * RHO * a ** 3 / 3   # carico d'aria su entrambe le facce (free air)


def derived(p, sd_m2, method, **kw):
    """Calcola Vas, Mms, Cms, Bl, ... con uno dei 4 metodi DATS."""
    fs, qes, qms, re = p["fs"], p["Qes"], p["Qms"], p["Re"]
    ws = 2 * math.pi * fs
    k = RHO * C_AIR ** 2 * sd_m2 ** 2   # Vas = k · Cms
    if method == "Scatola di test":
        vt = kw["vb_l"] / 1000
        vas = vt * (kw["fct"] * kw["qect"] / (fs * qes) - 1)
        cms = vas / k
        mms = 1 / (ws ** 2 * cms)
    elif method == "Massa aggiunta":
        ma = kw["ma_g"] / 1000
        mms = ma / ((fs / kw["fsa"]) ** 2 - 1)
        cms = 1 / (ws ** 2 * mms)
        vas = k * cms
    elif method == "SPL specificato":
        vas_ft3 = 10 ** ((kw["spl"] - 112.1) / 10) * qes / (2.7e-8 * fs ** 3)
        vas = vas_ft3 / FT3_PER_L / 1000
        cms = vas / k
        mms = 1 / (ws ** 2 * cms)
    elif method == "Mmd specificata":
        mms = kw["mmd_g"] / 1000 + air_load_mass(sd_m2)
        cms = 1 / (ws ** 2 * mms)
        vas = k * cms
    else:
        raise ValueError(method)
    bl = math.sqrt(ws * mms * re / qes)
    rms = ws * mms / qms
    vas_l = vas * 1000
    eta0 = 4 * math.pi ** 2 / C_AIR ** 3 * fs ** 3 * vas / qes   # = 2.7e-8·fs³·Vas[ft³]/Qes di DATS
    spl1w = 112.1 + 10 * math.log10(eta0) if eta0 > 0 else float("nan")
    rnom = p.get("Rnom") or 8
    out = {
        "Vas [L]": vas_l, "Cms [mm/N]": cms * 1000, "Mms [g]": mms * 1000,
        "Mmd [g]": (mms - air_load_mass(sd_m2)) * 1000, "BL [Tm]": bl, "Rms [kg/s]": rms,
        "η0 [%]": eta0 * 100, "SPL 1W/1m [dB]": spl1w,
        "SPL 2.83V/1m [dB]": spl1w + 10 * math.log10(8 / rnom) if np.isfinite(rnom) else float("nan"),
        "Sd [cm²]": sd_m2 * 1e4,
    }
    if method == "Massa aggiunta":
        shift = 1 - kw["fsa"] / fs
        out["_avviso"] = None if 0.25 <= shift <= 0.5 else (
            f"Lo spostamento di Fs è {shift*100:.0f}%: DATS consiglia 25–50%.")
    return out


# ---------------------------------------------------------------- R / L / C
def _accurate(f, z, zlo=1.0, zhi=2000.0, flo=20.0, fhi=20000.0):
    return (np.abs(z) >= zlo) & (np.abs(z) <= zhi) & (f >= flo) & (f <= fhi)


def resistor(f, z):
    m = (f >= 20) & (f <= 2000)
    return {"R [Ω]": float(np.median(z[m].real)), "X max [Ω]": float(np.max(np.abs(z[m].imag)))}


def inductor(f, z):
    w = 2 * np.pi * f
    m = _accurate(f, z) & (z.imag > 0.5)
    lval = float(np.median(z[m].imag / w[m])) if m.any() else float("nan")
    dcr = float(np.median(z[(f >= 10) & (f <= 50)].real))
    return {"L [mH]": lval * 1000, "DCR [Ω]": dcr}


def capacitor(f, z):
    w = 2 * np.pi * f
    m = _accurate(f, z) & (z.imag < -0.5)
    c = float(np.median(-1 / (w[m] * z[m].imag))) if m.any() else float("nan")
    rows = []
    for f0 in (120.0, 1000.0, 10000.0):
        zz = _value_at(f, z, f0)
        esr, xc = zz.real, -zz.imag
        df = esr / xc
        rows.append({"Frequenza [Hz]": f0, "ESR [Ω]": esr, "DF [%]": df * 100,
                     "Q": 1 / df if df else float("inf"), "δ [°]": math.degrees(math.atan(df))})
    return {"C [µF]": c * 1e6}, rows


# ---------------------------------------------------------------- rub & buzz
def within_geometric(value, ref, tol_pct):
    k = 1 + tol_pct / 100
    return ref / k <= value <= ref * k
