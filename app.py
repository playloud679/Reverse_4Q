"""DATS V3 — clone Streamlit multipiattaforma (interfaccia).

Avvio:  streamlit run app.py
Documentazione: docs/modules/app.md
"""
from __future__ import annotations

import datetime as dt
import importlib
import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from dats import __version__, calibration, dsp, export, hardware, params

# Streamlit tiene vivo il processo: ricarica i moduli del backend a ogni esecuzione
# (dsp prima di params e calibration, che ne importano funzioni)
for _mod in (hardware, dsp, calibration, params, export):
    importlib.reload(_mod)
CAL_FILE, Calibration = calibration.CAL_FILE, calibration.Calibration

st.set_page_config(page_title="DATS V3 Streamlit", page_icon="🔊", layout="wide")

CAL_LEVEL = -3.0  # dBFS: con lo sweep il canale di riferimento resta sotto ~0.6 FS

COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b",
          "#e377c2", "#7f7f7f", "#bcbd22"]

ss = st.session_state
ss.setdefault("cal", Calibration.load())
ss.setdefault("memories", [])
ss.setdefault("last", None)
ss.setdefault("vas", {})
ss.setdefault("rnb_ref", None)
ss.setdefault("rnb_log", [])


# =================================================================== sidebar
with st.sidebar:
    st.title("🔊 DATS V3")
    st.caption(f"v{__version__}")
    devs = hardware.list_devices()
    auto_in, auto_out = hardware.find_dats_devices()
    ins = [d for d in devs if d[2] >= 2]
    outs = [d for d in devs if d[3] >= 2]
    if auto_in is None:
        st.warning("DATS non rilevato automaticamente: seleziona i dispositivi.")

    def _pick(label, options, auto):
        idx = next((i for i, d in enumerate(options) if d[0] == auto), 0)
        return st.selectbox(label, options, index=idx, format_func=lambda d: d[1])[0] if options else None

    with st.expander("Dispositivo audio", expanded=auto_in is None):
        dev_in = _pick("Ingresso", ins, auto_in)
        dev_out = _pick("Uscita", outs, auto_out)
        fs_audio = st.selectbox("Frequenza di campionamento", [44100, 48000], index=0)
        swap = st.checkbox("Inverti canali di ingresso", False,
                           help="Default: IN sinistro = tensione sul DUT, IN destro = riferimento.")
    quality = st.selectbox("Risoluzione", list(dsp.QUALITY), index=0)
    exc_kind = dsp.EXCITATIONS[st.selectbox(
        "Segnale di test", list(dsp.EXCITATIONS), index=0,
        help="Lo sweep pilota il driver come il DATS originale (Fs e Q confrontabili). "
             "Il multitono, a parità di picco, pilota molto meno la risonanza.")]
    level = st.slider("Livello di misura [dBFS]", -50.0, -1.0, -3.0, 0.5,
                      help="Livello di picco del segnale di test. Con lo sweep, −3 dBFS riproduce "
                           "i risultati del DATS originale (+4 dBu).")
    st.divider()
    st.subheader("Grafico")
    log_z = st.toggle("Impedenza in scala log", True)
    show_reim = st.toggle("Mostra parte reale e immaginaria", False)
    fmin_plot, fmax_plot = st.select_slider(
        "Banda [Hz]", options=[1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000],
        value=(5, 20000))
    st.divider()
    cs = ss.cal.summary()
    st.caption("Calibrazione")
    st.write(("✅" if cs["1kΩ"] else "⚠️") + f" Rs = {cs['Rs @1kHz [Ω]']:.2f} Ω  ·  "
             + ("✅" if cs["corto"] else "⚠️") + f" puntali = {cs['Resistenza puntali [Ω]']:.3f} Ω")


def run_raw(level_db=None, quality_key=None, fmin=1.0, fmax=20000.0):
    """Misura grezza; se l'ingresso satura ripete a livello più basso (−6 dB, max 3 volte)."""
    if dev_in is None or dev_out is None:
        st.error("Nessun dispositivo audio selezionato.")
        st.stop()
    n, avg = dsp.QUALITY[quality_key or quality]
    lv = level if level_db is None else level_db
    for _ in range(4):
        try:
            raw = dsp.measure(dev_in, dev_out, fs_audio, n, avg, lv, fmin, fmax,
                              dut_ch=1 if swap else 0, ref_ch=0 if swap else 1, kind=exc_kind)
        except Exception as e:  # errori PortAudio
            st.error(f"Errore audio: {e}")
            st.stop()
        if not raw.clipped:
            return raw
        st.toast(f"Saturazione a {lv:.1f} dBFS: ripeto a {lv - 6:.1f} dBFS")
        lv -= 6
    st.warning(f"Ingresso ancora in saturazione (picco {raw.peak_in:.2f} FS).")
    return raw


def run_measure(level_db=None, quality_key=None, fmin=1.0, fmax=20000.0):
    """Esegue una misura e restituisce (f, Z per-bin, RawMeasurement)."""
    raw = run_raw(level_db, quality_key, fmin, fmax)
    return raw.f, ss.cal.apply(raw.f, raw.ratio), raw


def reduce(f, z, n=2500):
    return dsp.log_resample(f, z, n)


def impedance_fig(traces, height=520):
    """traces: lista di (nome, f, z, colore)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for name, f, z, col in traces:
        m = (f >= fmin_plot) & (f <= fmax_plot)
        f, z = f[m], z[m]
        fig.add_trace(go.Scatter(x=f, y=np.abs(z), name=f"|Z| {name}", line=dict(color=col, width=2)),
                      secondary_y=False)
        fig.add_trace(go.Scatter(x=f, y=np.degrees(np.angle(z)), name=f"fase {name}",
                                 line=dict(color=col, width=1, dash="dot")), secondary_y=True)
        if show_reim:
            fig.add_trace(go.Scatter(x=f, y=np.abs(z.real), name=f"Re {name}",
                                     line=dict(color="green", width=1)), secondary_y=False)
            fig.add_trace(go.Scatter(x=f, y=np.abs(z.imag), name=f"|Im| {name}",
                                     line=dict(color="purple", width=1)), secondary_y=False)
    fig.update_xaxes(type="log", title="Frequenza [Hz]", showgrid=True)
    fig.update_yaxes(type="log" if log_z else "linear", title="|Z| [Ω]", secondary_y=False)
    fig.update_yaxes(title="Fase [°]", range=[-90, 90], secondary_y=True, showgrid=False)
    fig.update_layout(height=height, hovermode="x unified", margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h", y=-0.15))
    return fig


def fmt_params(p: dict) -> pd.DataFrame:
    labels = {
        "fs": ("Fs", "Hz"), "Re": ("Re", "Ω"), "Zmax": ("Zmax", "Ω"), "Qms": ("Qms", ""),
        "Qes": ("Qes", ""), "Qts": ("Qts", ""), "f1": ("f1", "Hz"), "f2": ("f2", "Hz"),
        "Le@1k": ("Le @1 kHz", "mH"), "Le@10k": ("Le @10 kHz", "mH"), "Rnom": ("Z nominale", "Ω"),
        "Kr": ("Kr (Wright)", ""), "Xr": ("Xr (Wright)", ""), "Ki": ("Ki (Wright)", ""), "Xi": ("Xi (Wright)", ""),
    }
    rows = []
    for k, (lab, unit) in labels.items():
        if k in p and isinstance(p[k], (int, float)) and np.isfinite(p[k]):
            v = p[k] * 1000 if unit == "mH" else p[k]
            rows.append({"Parametro": lab, "Valore": f"{v:.4g}", "Unità": unit})
    return pd.DataFrame(rows)


def save_memory(name, f, z, p=None, kind="impedenza", notes=""):
    fr, zr = reduce(f, z)
    ss.memories.append({"name": name, "f": fr, "z": zr, "params": p or {}, "kind": kind,
                        "notes": notes, "time": dt.datetime.now().isoformat(timespec="seconds"),
                        "visible": True})


# =================================================================== tabs
t_imp, t_rlc, t_lin, t_rnb, t_mem, t_gen, t_cal = st.tabs(
    ["📈 Impedenza / T-S", "🧩 R · L · C", "📊 Linearità", "🐝 Rub & Buzz", "💾 Memorie",
     "〰️ Generatore / Scope", "🎯 Calibrazione"])

# ------------------------------------------------------------------- impedenza
with t_imp:
    if not ss.cal.summary()["1kΩ"]:
        st.info("Unità non calibrata: precisione ~10%. Esegui la calibrazione nella scheda 🎯.")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    do_fa = c1.button("▶ Parametri free-air", key="btn_free_air", type="primary", width="stretch")
    do_sw = c2.button("▶ Solo sweep impedenza", key="btn_sweep", width="stretch")
    re_override = c3.number_input("Re manuale [Ω] (0 = auto)", 0.0, 1000.0, 0.0, 0.01)
    with c4:
        fa_min, fa_max = st.select_slider("Ricerca risonanza [Hz]",
                                          options=[2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000],
                                          value=(5, 5000))
    if do_fa or do_sw:
        with st.spinner("Misura in corso…"):
            f, z, raw = run_measure()
        p = params.free_air(f, z, re_override or None, fa_min, fa_max) if do_fa else {}
        ss.last = {"f": f, "z": z, "params": p, "kind": "free-air" if do_fa else "sweep"}
        ss.vas = {}

    last = ss.last
    if last is not None:
        fr, zr = reduce(last["f"], last["z"])
        traces = [("Workbench", fr, zr, COLORS[0])]
        traces += [(m["name"], m["f"], m["z"], COLORS[(i + 1) % len(COLORS)])
                   for i, m in enumerate(ss.memories) if m.get("visible") and m.get("overlay")]
        g1, g2 = st.columns([3, 1])
        g1.plotly_chart(impedance_fig(traces), width="stretch")
        p = last["params"]
        with g2:
            if "errore" in p:
                st.error(p["errore"])
            elif p:
                for w in p.get("_avvisi", []):
                    st.warning(w)
                st.dataframe(fmt_params(p), hide_index=True, width="stretch", height=560)

        if p and "errore" not in p:
            st.subheader("Vas e parametri derivati")
            v1, v2 = st.columns([1, 2])
            with v1:
                method = st.radio("Metodo", ["Scatola di test", "Massa aggiunta", "SPL specificato",
                                             "Mmd specificata"], index=1)
                sd_mode = st.radio("Area pistone", ["Diametro", "Sd"], horizontal=True)
                if sd_mode == "Diametro":
                    dia = st.number_input("Diametro pistone [cm]", 1.0, 100.0, 8.0, 0.1,
                                          help="Diametro del cono incluso circa metà sospensione per lato.")
                    sd_m2 = params.piston_area(dia)
                else:
                    sd_m2 = st.number_input("Sd [cm²]", 1.0, 5000.0, 50.0, 0.5) / 1e4
            with v2:
                kw = {}
                if method == "Scatola di test":
                    kw["vb_l"] = st.number_input("Volume scatola chiusa Vt [L]", 0.1, 1000.0, 10.0, 0.1)
                    st.caption("Monta il driver sulla scatola e misura.")
                    if st.button("▶ Misura nella scatola", key="btn_vas_box"):
                        with st.spinner("Misura…"):
                            fb, zb, _ = run_measure()
                        pb = params.free_air(fb, zb, p["Re"], fa_min, fa_max)
                        if "errore" in pb:
                            st.error(f"Misura nella scatola: {pb['errore']}")
                        else:
                            ss.vas = {"fct": pb["fs"], "qect": pb["Qes"], "qmct": pb["Qms"], "fb": fb, "zb": zb}
                    if "fct" in ss.vas:
                        kw.update(fct=ss.vas["fct"], qect=ss.vas["qect"])
                        st.write(f"Fct = {ss.vas['fct']:.2f} Hz · Qect = {ss.vas['qect']:.3f} · Qmct = {ss.vas['qmct']:.3f}")
                elif method == "Massa aggiunta":
                    kw["ma_g"] = st.number_input("Massa aggiunta [g]", 0.1, 2000.0, 10.0, 0.1)
                    st.caption("Fissa la massa al cono (Fs deve scendere del 25–50%) e misura.")
                    if st.button("▶ Misura con massa aggiunta", key="btn_vas_mass"):
                        with st.spinner("Misura…"):
                            fb, zb, _ = run_measure()
                        pb = params.free_air(fb, zb, p["Re"], fa_min, p["fs"] * 1.05)
                        if "errore" in pb:
                            st.error(f"Misura con massa: {pb['errore']}")
                        else:
                            ss.vas = {"fsa": pb["fs"], "fb": fb, "zb": zb}
                    if "fsa" in ss.vas:
                        kw["fsa"] = ss.vas["fsa"]
                        st.write(f"Fs con massa = {ss.vas['fsa']:.2f} Hz")
                elif method == "SPL specificato":
                    kind_spl = st.radio("Riferimento", ["1 W / 1 m", "2.83 V / 1 m"], horizontal=True)
                    spl = st.number_input("SPL dichiarato [dB]", 60.0, 120.0, 87.0, 0.1)
                    if kind_spl.startswith("2.83"):
                        spl -= 10 * math.log10(8 / (p.get("Rnom") or 8))
                    kw["spl"] = spl
                else:
                    kw["mmd_g"] = st.number_input("Mmd (massa mobile senza aria) [g]", 0.01, 2000.0, 10.0, 0.01)

                ready = method in ("SPL specificato", "Mmd specificata") or \
                    ("fct" in kw) or ("fsa" in kw)
                if ready:
                    try:
                        d = params.derived(p, sd_m2, method, **kw)
                        warn = d.pop("_avviso", None)
                        if warn:
                            st.warning(warn)
                        p_all = {**p, **{k: v for k, v in d.items()}}
                        last["params"] = p_all
                        st.dataframe(pd.DataFrame([{"Parametro": k, "Valore": f"{v:.4g}"} for k, v in d.items()]),
                                     hide_index=True, width="stretch")
                    except (ValueError, ZeroDivisionError, KeyError) as e:
                        st.error(f"Impossibile calcolare: {e}")
                if "zb" in ss.vas:
                    fb2, zb2 = reduce(ss.vas["fb"], ss.vas["zb"])
                    st.plotly_chart(impedance_fig([("free-air", fr, zr, COLORS[0]),
                                                   ("seconda misura", fb2, zb2, COLORS[1])], 320),
                                    width="stretch")

        st.divider()
        s1, s2, s3, s4 = st.columns([2, 3, 1, 1])
        mname = s1.text_input("Nome", f"Misura {len(ss.memories) + 1}")
        mnotes = s2.text_input("Note", "")
        if s3.button("💾 Salva in memoria", key="btn_mem_save", width="stretch"):
            save_memory(mname, last["f"], last["z"], last["params"], last["kind"], mnotes)
            st.toast(f"Salvato: {mname}")
        with s4:
            st.download_button(".zma", key="btn_dl_zma", data=export.to_zma(fr, zr), file_name=f"{mname}.zma", width="stretch")
            st.download_button(".txt", key="btn_dl_txt", data=export.params_txt(mname, mnotes, last["params"]),
                               file_name=f"{mname}.txt", width="stretch")

# ------------------------------------------------------------------- R L C
with t_rlc:
    st.caption(f"Come in DATS, i componenti si misurano al livello massimo ({CAL_LEVEL:.0f} dBFS).")
    comp = st.radio("Componente", ["Resistore", "Induttore", "Condensatore"], horizontal=True)
    if st.button("▶ Misura componente", key="btn_rlc", type="primary"):
        with st.spinner("Misura…"):
            f, z, _ = run_measure(level_db=CAL_LEVEL)
        fr, zr = reduce(f, z)
        if comp == "Resistore":
            res = params.resistor(f, z)
            st.metric("R", f"{res['R [Ω]']:.4g} Ω")
        elif comp == "Induttore":
            res = params.inductor(f, z)
            a, b = st.columns(2)
            a.metric("L", f"{res['L [mH]']:.4g} mH")
            b.metric("DCR", f"{res['DCR [Ω]']:.4g} Ω")
        else:
            res, rows = params.capacitor(f, z)
            st.metric("C", f"{res['C [µF]']:.4g} µF")
            st.dataframe(pd.DataFrame(rows).style.format("{:.4g}"), hide_index=True)
        ss.last = {"f": f, "z": z, "params": res, "kind": comp.lower()}
        st.plotly_chart(impedance_fig([(comp, fr, zr, COLORS[0])], 420), width="stretch")

# ------------------------------------------------------------------- linearità
with t_lin:
    st.caption("Misura i parametri free-air a più livelli (DATS Linearity Test).")
    l1, l2, l3, l4 = st.columns(4)
    top = l1.number_input("Livello massimo [dBFS]", -40.0, -3.0, -6.0, 0.5)
    nsw = l2.number_input("Numero di sweep", 2, 10, 3)
    step = l3.number_input("Passo [dB]", 1.0, 20.0, 10.0, 1.0)
    direction = l4.radio("Direzione", ["Decrescente", "Crescente"])
    if st.button("▶ Avvia test di linearità", key="btn_linearity", type="primary"):
        lv = [top - i * step for i in range(int(nsw))]
        if direction == "Crescente":
            lv = lv[::-1]
        rows, traces = [], []
        bar = st.progress(0.0)
        for i, L in enumerate(lv):
            f, z, _ = run_measure(level_db=L)
            p = params.free_air(f, z, None)
            fr, zr = reduce(f, z)
            traces.append((f"{L:.0f} dBFS", fr, zr, COLORS[i % len(COLORS)]))
            save_memory(f"Linearità {L:.0f} dBFS", f, z, p, "linearità")
            rows.append({"Livello [dBFS]": L, **{k: p.get(k) for k in ("fs", "Re", "Zmax", "Qms", "Qes", "Qts")}})
            bar.progress((i + 1) / len(lv))
        st.dataframe(pd.DataFrame(rows).style.format("{:.4g}"), hide_index=True)
        st.plotly_chart(impedance_fig(traces), width="stretch")

# ------------------------------------------------------------------- rub & buzz
with t_rnb:
    st.caption("Confronta Fs e Zmax di ogni driver, misurato a livello ridotto, con un campione di riferimento.")
    r1, r2, r3 = st.columns(3)
    rnb_lvl = r1.slider("Livello di test [dB rispetto al normale]", -50, 0, -30)
    tol_fs = r2.number_input("Tolleranza Fs [%]", 1.0, 500.0, 40.0)
    tol_z = r3.number_input("Tolleranza Zmax [%]", 1.0, 500.0, 100.0)
    a, b = st.columns(2)
    if a.button("1️⃣ Misura riferimento (driver buono)", key="btn_rnb_ref"):
        f, z, _ = run_measure()
        p = params.free_air(f, z)
        if "errore" in p:
            st.error(f"Riferimento non valido: {p['errore']}")
        else:
            ss.rnb_ref = {"f": f, "z": z, "p": p}
            ss.rnb_log = []
    if ss.rnb_ref is not None:
        rp = ss.rnb_ref["p"]
        st.write(f"Riferimento: Fs = {rp['fs']:.2f} Hz · Zmax = {rp['Zmax']:.2f} Ω")
        if b.button("2️⃣ Testa driver", key="btn_rnb_test", type="primary"):
            f, z, _ = run_measure(level_db=level + rnb_lvl)
            p = params.free_air(f, z)
            ok_fs = "fs" in p and params.within_geometric(p["fs"], rp["fs"], tol_fs)
            ok_z = "Zmax" in p and params.within_geometric(p["Zmax"], rp["Zmax"], tol_z)
            ok = ok_fs and ok_z
            ss.rnb_log.append({"#": len(ss.rnb_log) + 1, "Esito": "PASS" if ok else "FAIL",
                               "Fs": p.get("fs"), "Zmax": p.get("Zmax")})
            if ok:
                st.success("# ✅ PASS")
            else:
                st.error("# ❌ FAIL — " + ("Fs fuori tolleranza " if not ok_fs else "") +
                         ("Zmax fuori tolleranza" if not ok_z else ""))
            fr, zr = reduce(f, z)
            f0, z0 = reduce(ss.rnb_ref["f"], ss.rnb_ref["z"])
            st.plotly_chart(impedance_fig([("riferimento", f0, z0, COLORS[0]), ("test", fr, zr, COLORS[1])], 380),
                            width="stretch")
        if ss.rnb_log:
            st.dataframe(pd.DataFrame(ss.rnb_log), hide_index=True)

# ------------------------------------------------------------------- memorie
with t_mem:
    if not ss.memories:
        st.info("Nessuna memoria salvata.")
    else:
        for i, m in enumerate(ss.memories):
            c = st.columns([3, 4, 1, 1, 1])
            m["name"] = c[0].text_input("Nome", m["name"], key=f"temp_mem_name_{i}", label_visibility="collapsed")
            m["notes"] = c[1].text_input("Note", m.get("notes", ""), key=f"temp_mem_notes_{i}", label_visibility="collapsed")
            m["visible"] = c[2].checkbox("Mostra", m.get("visible", True), key=f"temp_mem_visible_{i}")
            m["overlay"] = c[3].checkbox("Su workbench", m.get("overlay", False), key=f"temp_mem_overlay_{i}")
            if c[4].button("🗑", key=f"btn_mem_delete_{i}"):
                ss.memories.pop(i)
                st.rerun()
        vis = [(m["name"], m["f"], m["z"], COLORS[i % len(COLORS)]) for i, m in enumerate(ss.memories) if m["visible"]]
        if vis:
            st.plotly_chart(impedance_fig(vis), width="stretch")
        tab = []
        for m in ss.memories:
            if m["visible"] and m["params"]:
                tab.append({"Nome": m["name"], **{k: v for k, v in m["params"].items()
                                                   if isinstance(v, (int, float)) and not k.startswith("_")}})
        if tab:
            st.dataframe(pd.DataFrame(tab).set_index("Nome").T.style.format("{:.4g}", na_rep="—"))
    st.divider()
    p1, p2, p3 = st.columns(3)
    p1.download_button("⬇ Salva progetto (.json)", key="btn_dl_project", data=export.project_json(ss.memories),
                       file_name="progetto_dats.json", disabled=not ss.memories)
    up = p2.file_uploader("Carica progetto", type=["json"])
    if up is not None and p2.button("Apri progetto", key="btn_project_open"):
        ss.memories = export.project_load(up.getvalue().decode())
        st.rerun()
    upz = p3.file_uploader("Importa .zma e calcola parametri", type=["zma", "txt", "frd"])
    if upz is not None and p3.button("Importa", key="btn_zma_import"):
        f, z = export.from_zma(upz.getvalue().decode(errors="ignore"))
        p = params.free_air(f, z)
        save_memory(upz.name, f, z, p, "importato")
        st.rerun()

# ------------------------------------------------------------------- generatore / scope
with t_gen:
    st.caption("Il segnale esce dal canale sinistro (puntali). Lo scope mostra i due ingressi: "
               "riferimento (generatore) e tensione sul DUT.")
    g1, g2, g3, g4 = st.columns(4)
    kind = g1.selectbox("Forma d'onda", ["Sinusoide", "Quadra", "Triangolare", "Dente di sega", "Impulsi",
                                          "Rumore rosa", "Rumore bianco", "Sweep logaritmico"])
    freq = g2.number_input("Frequenza [Hz]", 1.0, 20000.0, 1000.0)
    glev = g3.slider("Livello [dBFS]", -60.0, 0.0, -10.0, 0.5)
    dur = g4.number_input("Durata [s]", 0.2, 30.0, 2.0)
    vfs = st.number_input("Volt di picco a 0 dBFS (opzionale, misurati con un multimetro; 0 = mostra in FS)",
                          0.0, 20.0, 0.0, 0.01)
    if st.button("▶ Genera e acquisisci", key="btn_generate", type="primary"):
        y = dsp.generate(kind, fs_audio, dur, freq, glev)
        out = np.zeros((len(y), 2))
        out[:, 0] = y
        try:
            rec = hardware.playrec(out, fs_audio, dev_in, dev_out)
        except Exception as e:
            st.error(f"Errore audio: {e}")
            st.stop()
        k = vfs or 1.0
        unit = "V" if vfs else "FS"
        ref = rec[:, 0 if swap else 1] * k
        dut = rec[:, 1 if swap else 0] * k
        mid = len(rec) // 2
        span = int(min(len(rec) // 2 - 1, max(3 * fs_audio / max(freq, 1), 0.01 * fs_audio)))
        t = np.arange(-span, span) / fs_audio * 1000
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=ref[mid - span:mid + span], name="Riferimento"))
        fig.add_trace(go.Scatter(x=t, y=dut[mid - span:mid + span], name="DUT"))
        fig.update_layout(height=350, xaxis_title="ms", yaxis_title=unit, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")
        seg = ref[len(ref) // 4: 3 * len(ref) // 4]
        Y = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) / (len(seg) / 4)
        ff = np.fft.rfftfreq(len(seg), 1 / fs_audio)
        fig2 = go.Figure(go.Scatter(x=ff[1:], y=20 * np.log10(Y[1:] + 1e-12), name="Spettro riferimento"))
        fig2.update_xaxes(type="log", title="Hz")
        fig2.update_yaxes(title=f"dB{unit}")
        fig2.update_layout(height=300, margin=dict(t=20))
        st.plotly_chart(fig2, width="stretch")
        rms = lambda s: float(np.sqrt(np.mean(s[len(s) // 4: 3 * len(s) // 4] ** 2)))
        st.write(f"RMS riferimento = {rms(ref):.4g} {unit} · RMS DUT = {rms(dut):.4g} {unit}")

# ------------------------------------------------------------------- calibrazione
with t_cal:
    st.markdown(
        """
**Procedura** (come nel software originale, più la misura a vuoto):
1. **Aperto** – puntali scollegati e separati.
2. **1 kΩ** – puntali sui due terminali metallici di calibrazione sul frontale.
3. **Corto** – coccodrilli pinzati tra loro.

La calibrazione viene salvata in `""" + str(CAL_FILE) + "`.")
    rcal = st.number_input("Valore del resistore di calibrazione [Ω]", 100.0, 10000.0,
                           float(ss.cal.r_cal_ohm), 0.1)
    cal_q = list(dsp.QUALITY)[-1]
    k1, k2, k3, k4 = st.columns(4)
    if k1.button("1️⃣ Aperto", key="btn_cal_open", width="stretch"):
        with st.spinner("Misura a vuoto…"):
            raw = run_raw(CAL_LEVEL, cal_q)
        ss.cal.set_open(raw.f, raw.ratio)
        ss.cal.save()
        st.success(f"Rapporto a vuoto @1 kHz = {abs(ss.cal.r_open_at(np.array([1000.0]))[0]):.5f}")
    if k2.button("2️⃣ 1 kΩ", key="btn_cal_load", width="stretch"):
        with st.spinner("Misura del resistore di riferimento…"):
            raw = run_raw(CAL_LEVEL, cal_q)
        ss.cal.set_load(raw.f, raw.ratio, rcal)
        ss.cal.save()
        st.success(f"Rs @1 kHz = {ss.cal.rs_at(np.array([1000.0]))[0].real:.3f} Ω")
    if k3.button("3️⃣ Corto", key="btn_cal_short", width="stretch"):
        with st.spinner("Misura dei puntali in corto…"):
            raw = run_raw(CAL_LEVEL, cal_q)
        ss.cal.set_short(raw.f, raw.ratio)
        ss.cal.save()
        st.success(f"Resistenza puntali = {ss.cal.z_lead_at(np.array([100.0]))[0].real:.4f} Ω")
    if k4.button("↺ Ripristina default", key="btn_cal_reset", width="stretch"):
        ss.cal.reset()
        ss.cal.save()
        st.rerun()
    st.divider()
    if st.button("✔ Verifica: misura il carico collegato", key="btn_cal_verify"):
        f, z, _ = run_measure(level_db=CAL_LEVEL)
        fr, zr = reduce(f, z)
        st.metric("R misurata (20 Hz–2 kHz)", f"{params.resistor(f, z)['R [Ω]']:.4f} Ω")
        st.plotly_chart(impedance_fig([("verifica", fr, zr, COLORS[0])], 380), width="stretch")
    st.json(ss.cal.summary())
