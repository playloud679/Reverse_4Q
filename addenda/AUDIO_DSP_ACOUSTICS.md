# Audio DSP & Acoustic Test Benches Standard

**Specification Addendum:** `STD-ADD-ACOUSTICS-V1.0`

Guidelines and invariants for acoustic simulation engines, Thiele/Small parameter extraction, impedance analyzers, loudspeaker modeling, and audio acquisition pipelines.

---

> **antirez style reminder:** minimalism, near-zero dependencies, efficiency, zero complexity. DSP code also follows the antirez style: solve the physics with the smallest correct implementation, prefer the standard library, and reject unnecessary complexity.

## 1. Electroacoustic Invariants

All simulation models and parameter extractors must respect electroacoustic physics:

1. **Impedance Bounds**:
   - $Z_{\text{max}} > R_e > 0$
   - Real part $\text{Re}(Z(f)) > 0$ for all frequencies in passive loads.
   - Half-power bandwidth $f_2 > f_1 > 0$ with $f_s \in (f_1, f_2)$.

2. **Thiele/Small Consistency**:
   - $Q_{ts} = \frac{Q_{ms} \cdot Q_{es}}{Q_{ms} + Q_{es}} < \min(Q_{es}, Q_{ms})$
   - Reference efficiency $\eta_0 = \frac{4\pi^2}{c^3} \cdot \frac{f_s^3 \cdot V_{as}}{Q_{es}}$
   - Force factor $BL = \sqrt{\frac{2\pi f_s \cdot M_{ms} \cdot R_e}{Q_{es}}}$

3. **Lossy Voice Coil Inductance ($L_e$)**:
   - Voice coil inductance is non-ideal due to iron pole eddy currents (semi-inductance).
   - Always evaluate and report inductance at standard spot frequencies:
     - $L_e @ 1\text{ kHz}$
     - $L_e @ 10\text{ kHz}$
   - In single-inductor approximations:
     $$L_e(f) = \frac{\text{Im}(Z(f))}{2\pi f}$$

---

## 2. Resonance Peak Extraction & Half-Power Points

1. **Peak Discrimination**:
   - Never use a global `argmax(|Z|)` across the full audible range (20 Hz–20 kHz). At high frequencies ($> 5\text{ kHz}$), inductive rise $j\omega L_e$ frequently exceeds the mechanical resonance magnitude $Z_{\text{max}}$.
   - Always find internal local maxima ($\frac{d|Z|}{df} = 0$, $\frac{d^2|Z|}{df^2} < 0$) with phase zero-crossings (capacitive $\to$ inductive motional transition).

2. **Half-Power Resolution ($f_1, f_2$)**:
   - Half-power threshold: $Z_{1,2} = \sqrt{R_e \cdot Z_{\text{max}}}$.
   - Find $f_1$ by descending from peak towards DC.
   - Find $f_2$ by ascending from peak towards high frequency.
   - **Geometric Mean Fallback**: If $f_2$ is masked by voice coil inductance before $|Z|$ descends to $Z_{1,2}$, compute:
     $$f_2 = \frac{f_s^2}{f_1}$$
   - If $f_1$ is masked by low-frequency measurement limits, compute:
     $$f_1 = \frac{f_s^2}{f_2}$$

---

## 3. Audio Acquisition & Duplex Hardware Safety

1. **Device Validation**:
   - Validate stereo input and stereo output channels ($\ge 2$) before initiating any audio stream.
   - Check host API and sample rate compatibility (standard: 44.1 kHz, 16/24-bit).
   - Gracefully handle empty or disconnected audio devices without crashing the UI.

2. **Latency Cushion & Chirp Tracking**:
   - Add leading and trailing latency cushions (e.g. $\ge 0.5\text{ s}$) around acquisition to prevent truncating chirp boundaries.
   - Log-swept sine signals require post-sweep recording time ($\ge 0.5\text{ s}$) to capture room/system latency tails without truncating high frequencies at 20 kHz.
   - Prefer tracking coherent demodulation / channel-ratio analysis over naive global FFTs.
