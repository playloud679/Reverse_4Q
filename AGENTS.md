# Agent Instructions for AI Coding Assistants

This project adheres to [`GOLDEN_STD.md`](GOLDEN_STD.md) (spec `1.5.0`, synced from
`playloud679/dev_standards` @ `607da03`). Precedence: explicit user instructions → project
constraints below → `GOLDEN_STD.md`.

## Project facts

- **Lifecycle stage:** Alpha (`0.x.y`). `1.0.0` is locked until Beta exit.
  Beta criteria: all tabs verified on hardware against the original DATS on at least 3 drivers and
  1 R, L, C each; macOS and Linux runs confirmed.
- **Integration branch:** `main`. Work on a dedicated branch (`feat/…`, `fix/…`, `docs/…`,
  `chore/…`); open a draft PR to `main`.
- **Applicable addenda:** [`addenda/AUDIO_DSP_ACOUSTICS.md`](addenda/AUDIO_DSP_ACOUSTICS.md),
  [`addenda/STREAMLIT_SAAS.md`](addenda/STREAMLIT_SAAS.md). Not applicable: embedded firmware.
- **Module docs:** [`docs/INDEX.md`](docs/INDEX.md) maps every source file to its document.
- **Version sources:** `VERSION`, `dats/__init__.py` (`__version__`, shown in the UI sidebar),
  README badge, `CHANGELOG.md`. Keep all four in sync on every application patch.

## Sources of truth (GOLDEN_STD §16)

| Artifact | Kind |
|---|---|
| `app.py`, `dats/*.py`, `tests/*.py`, `docs/**`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `VERSION` | hand-edited |
| `GOLDEN_STD.md`, `addenda/*.md` | copied from `dev_standards`; do not edit locally, re-sync instead |
| `Exported Impedance Data.txt` | measurement exported by the original DATS software; test fixture, never regenerate |
| `%APPDATA%/dats_streamlit/calibration.json` | generated at runtime by the calibration tab; per-machine, not in git |

## Rule 0: Modular development, comments, and dedicated documentation

Each module has a module docstring pointing to its `docs/modules/…` file and an entry in
`docs/INDEX.md`. After every source patch, review affected module docs and comments; update what is
inaccurate, leave accurate docs unchanged and report the review. Follow `GOLDEN_STD.md` §0 and §2.

## Rule 1: Validation proportional to impact

```bash
python -m py_compile app.py dats/*.py
python -m unittest discover -s tests -v
```

The suite is offline (no DATS needed) and includes a headless `AppTest`. Hardware behaviour
(calibration, live measurements) is verified manually with the DATS connected; report it as such.
Documentation-only patches: `git diff --check` and link checks; the suite is not required.

## Rule 2: Mandatory version bump

Every application patch bumps the version (patch for fixes/UX, minor for features) and updates
`CHANGELOG.md` with date, summary and actual validation results. Docs/tests-only patches do not bump.
Commit, tag, push and release only when the user asks. See `GOLDEN_STD.md` §8.

## Rule 3: antirez style

Minimalism, near-zero dependencies, efficiency, no complexity (`GOLDEN_STD.md` §17).
Runtime dependencies and why they stay:

- `numpy`: all DSP and fitting. SciPy is deliberately **not** used (its LAPACK DLLs are blocked by
  Windows Smart App Control on the dev machine; peak search, polynomial refinement and
  Levenberg–Marquardt are implemented in NumPy).
- `sounddevice`: the only portable PortAudio binding; isolated in `dats/hardware.py`.
- `streamlit`: the requested UI framework; only `app.py` imports it.
- `plotly`: log-frequency axes with dual y (|Z| and phase), which Streamlit's built-in charts lack;
  only `app.py` imports it.
- `pandas`: already a Streamlit dependency; used only for table formatting in `app.py`.

Tests use the standard library `unittest`, not pytest.
