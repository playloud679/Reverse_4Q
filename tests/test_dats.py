"""Test offline (senza hardware) dei moduli dats/* e smoke test dell'interfaccia.

Avvio:  python -m unittest discover -s tests -v
"""
import math
import pathlib
import sys
import unittest

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dats import dsp, export, params  # noqa: E402
from dats.calibration import Calibration  # noqa: E402

FS = 44100
F = np.fft.rfftfreq(2**16, 1 / FS)
F = F[(F >= 1) & (F <= 20000)]


def driver(f, re=6.0, res=30.0, fs=50.0, qms=4.0, le=0.5e-3):
    return re + res / (1 + 1j * qms * (f / fs - fs / f)) + 1j * 2 * np.pi * f * le


class FreeAir(unittest.TestCase):
    def test_synthetic_driver(self):
        p = params.free_air(F, driver(F))
        self.assertAlmostEqual(p["fs"], 50.0, delta=0.25)
        self.assertAlmostEqual(p["Re"], 6.0, delta=0.03)
        self.assertAlmostEqual(p["Qms"], 4.0, delta=0.1)
        self.assertAlmostEqual(p["Qes"], 4.0 * 6 / 30, delta=0.03)
        self.assertLess(p["Qts"], min(p["Qms"], p["Qes"]))
        self.assertTrue(0 < p["f1"] < p["fs"] < p["f2"])
        self.assertGreater(p["Zmax"], p["Re"])
        self.assertAlmostEqual(p["Le@1k"], 0.5e-3, delta=0.02e-3)
        self.assertAlmostEqual(p["Le@10k"], 0.5e-3, delta=0.02e-3)
        self.assertEqual(p["_avvisi"], [])

    def test_inductive_rise_does_not_hide_resonance(self):
        # con Le grande |Z| a 20 kHz supera Zmax: la risonanza resta quella a 50 Hz
        f = F[F <= 20000]
        z = driver(f, le=3e-3)
        self.assertGreater(abs(z[-1]), 36)
        self.assertAlmostEqual(params.free_air(f, z)["fs"], 50.0, delta=0.5)

    def test_f2_masked_uses_geometric_mean(self):
        f = F[F <= 58]   # f2 (~57 Hz) fuori dai dati
        p = params.free_air(f, driver(f), fmax=58)
        self.assertNotIn("errore", p)
        self.assertTrue(any("f2" in w for w in p["_avvisi"]))
        self.assertAlmostEqual(p["f2"], p["fs"] ** 2 / p["f1"], places=6)

    def test_no_resonance_is_an_error(self):
        p = params.free_air(F, np.full(len(F), 8.0 + 0j))
        self.assertIn("errore", p)

    def test_wright_recovers_constants(self):
        w = 2 * np.pi * F
        z = 6.0 + 0.05 * w ** 0.6 + 1j * 0.002 * w ** 0.8
        p = params.wright(F, z, 6.0)
        self.assertAlmostEqual(p["Xr"], 0.6, places=3)
        self.assertAlmostEqual(p["Xi"], 0.8, places=3)
        self.assertAlmostEqual(p["Kr"], 0.05, delta=1e-3)
        self.assertAlmostEqual(p["Ki"], 0.002, delta=1e-4)
        # induttore ideale: nessuna parte reale oltre Re → nessun parametro, nessun NaN
        self.assertEqual(params.wright(F, 6.0 + 1j * 2 * np.pi * F * 1e-3, 6.0), {})


class Derived(unittest.TestCase):
    P = {"fs": 50.0, "Qes": 0.8, "Qms": 4.0, "Re": 6.0, "Rnom": 8}

    def test_mmd_method_relations(self):
        sd = params.piston_area(16.5)
        d = params.derived(self.P, sd, "Mmd specificata", mmd_g=20.0)
        ws = 2 * math.pi * 50
        mms = d["Mms [g]"] / 1000
        self.assertAlmostEqual(d["Mmd [g]"], 20.0, places=6)
        self.assertAlmostEqual(d["BL [Tm]"], math.sqrt(ws * mms * 6 / 0.8), places=6)
        self.assertAlmostEqual(d["Cms [mm/N]"] / 1000, 1 / (ws ** 2 * mms), places=9)
        # η0 SI coincide con la formula DATS in piedi cubi
        eta_dats = 2.7e-8 * 50 ** 3 * d["Vas [L]"] * params.FT3_PER_L / 0.8
        self.assertAlmostEqual(d["η0 [%]"] / 100, eta_dats, delta=eta_dats * 0.01)

    def test_methods_agree(self):
        sd = params.piston_area(16.5)
        ref = params.derived(self.P, sd, "Mmd specificata", mmd_g=20.0)
        mms = ref["Mms [g]"]
        fsa = 50 / math.sqrt(1 + 10 / mms)   # massa aggiunta di 10 g
        added = params.derived(self.P, sd, "Massa aggiunta", ma_g=10.0, fsa=fsa)
        self.assertAlmostEqual(added["Vas [L]"], ref["Vas [L]"], delta=ref["Vas [L]"] * 1e-6)
        spl = params.derived(self.P, sd, "SPL specificato", spl=ref["SPL 1W/1m [dB]"])
        self.assertAlmostEqual(spl["Vas [L]"], ref["Vas [L]"], delta=ref["Vas [L]"] * 0.01)


class Components(unittest.TestCase):
    def test_resistor_inductor_capacitor(self):
        w = 2 * np.pi * F
        self.assertAlmostEqual(params.resistor(F, np.full(len(F), 47.0 + 0j))["R [Ω]"], 47.0)
        ind = params.inductor(F, 0.4 + 1j * w * 1.5e-3)
        self.assertAlmostEqual(ind["L [mH]"], 1.5, places=6)
        self.assertAlmostEqual(ind["DCR [Ω]"], 0.4, places=6)
        cap, rows = params.capacitor(F, 0.1 - 1j / (w * 10e-6))
        self.assertAlmostEqual(cap["C [µF]"], 10.0, places=4)
        self.assertAlmostEqual(rows[1]["ESR [Ω]"], 0.1, places=6)

    def test_geometric_tolerance(self):
        self.assertTrue(params.within_geometric(25.0, 50.0, 100))
        self.assertTrue(params.within_geometric(100.0, 50.0, 100))
        self.assertFalse(params.within_geometric(24.0, 50.0, 100))


class Calib(unittest.TestCase):
    def test_open_short_load_round_trip(self):
        rs = 94.0 + 0.2j + 1j * 2 * np.pi * F * 1e-7
        r_open = 0.997 * np.exp(-1j * 2 * np.pi * F * 2e-8)
        lead = 0.7 + 1j * 2 * np.pi * F * 0.8e-6
        ratio = lambda z: r_open * z / (rs + z)
        c = Calibration()
        c.set_open(F, r_open)
        c.set_load(F, ratio(1000.0 + lead), 1000.0)
        c.set_short(F, ratio(lead))
        z = driver(F)
        out = c.apply(F, ratio(z + lead))
        m = (F > 5) & (F < 15000)
        self.assertLess(np.max(np.abs(out[m] - z[m]) / np.abs(z[m])), 2e-3)
        self.assertAlmostEqual(c.summary()["Resistenza puntali [Ω]"], 0.7, delta=1e-3)

    def test_serialization(self):
        c = Calibration()
        c.set_open(F, np.full(len(F), 0.99 + 0j))
        d = Calibration.from_dict(c.to_dict())
        np.testing.assert_allclose(d.r_open, c.r_open)
        self.assertIsNone(d.r_load)


class Signals(unittest.TestCase):
    def test_excitations_are_periodic_and_bounded(self):
        for kind in ("sweep", "multitone"):
            x, band = dsp.excitation(2**15, FS, kind=kind)
            self.assertAlmostEqual(np.max(np.abs(x)), 1.0)
            X = np.fft.rfft(x)
            self.assertLess(np.max(np.abs(X[~band])), 1e-9 * np.max(np.abs(X)))
            self.assertLess(1 / np.sqrt(np.mean(x ** 2)), 2.5)   # fattore di cresta

    def test_log_resample_keeps_values(self):
        f, z = dsp.log_resample(F, np.full(len(F), 3 + 4j), 200)
        np.testing.assert_allclose(z, 3 + 4j)
        self.assertTrue(np.all(np.diff(f) > 0))


class Export(unittest.TestCase):
    def test_zma_round_trip(self):
        z = driver(F[::50])
        f, z2 = export.from_zma(export.to_zma(F[::50], z))
        np.testing.assert_allclose(np.abs(z2), np.abs(z), rtol=1e-4)

    def test_original_dats_export_regression(self):
        # export del software originale, stesso driver misurato con l'app (README)
        text = (ROOT / "Exported Impedance Data.txt").read_text(encoding="latin-1")
        f, z = export.from_zma(text)
        self.assertEqual(len(f), 344)
        p = params.free_air(f, z)
        self.assertAlmostEqual(p["fs"], 132.9, delta=1.0)
        self.assertAlmostEqual(p["Qts"], 0.567, delta=0.02)


class UI(unittest.TestCase):
    def test_app_renders(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("streamlit non installato")
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
        at.run()
        self.assertFalse(at.exception, at.exception)
        self.assertEqual(len(at.tabs), 7)


if __name__ == "__main__":
    unittest.main()
