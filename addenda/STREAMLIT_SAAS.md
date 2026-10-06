# Streamlit & SaaS Web Dashboard Standard

**Specification Addendum:** `STD-ADD-STREAMLIT-V1.0`

Guidelines and state isolation patterns for Streamlit dashboards, Cloud Run deployments, and SaaS web applications.

---

> **antirez style reminder:** minimalism, near-zero dependencies, efficiency, zero complexity. Dashboard code also follows the antirez style: keep state and UI minimal, avoid extra dependencies, and eliminate unnecessary complexity.

## 1. Widget State Key Isolation

In Streamlit, avoid `StreamlitValueAssignmentNotAllowedError` by strictly separating interactive button/action keys from persistent parameter keys:

- **Serializable Model Parameters**: Use domain prefixes, e.g.:
  - `driver_fs_hz`, `driver_qts`, `box_vb_l`, `port_fb_hz`
- **Interactive Action Buttons / Trigger Keys**: Use dedicated action prefixes:
  - `btn_apply_combo`, `btn_calculate_ts`, `action_reset`
- **Temporary Widget Keys**: Use a distinct prefix such as `temp_` and exclude these keys from persistent parameter serialization.
- **Rule**: Action buttons and modal triggers must NEVER share a prefix with the model parameter dictionary or session-state collection loop.

---

## 2. Dynamic Module Reloading

Streamlit runs in a long-lived Python process. When developing modular backend components under `src/`:

```python
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
import my_engine

importlib.reload(my_engine)
```

---

## 3. Headless UI Testing

For patches affecting Streamlit rendering or its backend integration, run a headless AppTest as a focused UI check. Documentation-only changes do not require it. Broader validation follows [the core testing contract](../GOLDEN_STD.md#7-testing):

```bash
python -c 'from streamlit.testing.v1 import AppTest; at = AppTest.from_file("app.py", default_timeout=30); at.run(); assert not at.exception, at.exception'
```
