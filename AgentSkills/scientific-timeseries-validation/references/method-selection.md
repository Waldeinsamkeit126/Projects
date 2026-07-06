# Time-series method selection

Use this reference after inventorying the dataset and checking units and sampling.

## Decision table

| Data condition | Prefer | Avoid or qualify |
|---|---|---|
| Regular sampling; stable periodicity | Periodogram, FFT, Welch | Reading the largest raw FFT bin without detrending or window checks |
| Irregular sampling | Lomb-Scargle | Plain FFT on raw timestamps |
| Frequency changes over time | STFT or wavelet analysis | One global spectrum as the whole answer |
| Strong trend or DC offset | Model/detrend first; analyze residuals | Treating low-frequency trend as a cycle |
| Short record or fewer than 3 cycles | Report weak evidence; collect more data | A precise period claim |
| Large gaps | Segment, use a gap-aware method, or justify interpolation | Silent interpolation across long gaps |
| Abrupt changes or spikes | Robust rolling statistics or change-point methods | Using only global mean and standard deviation |
| Multiple channels | Cross-correlation, coherence, or aligned feature comparison | Comparing unaligned timestamps |

## FFT gate

Use ordinary FFT/Welch only when all relevant conditions hold:

1. Timestamps are strictly increasing.
2. Sampling intervals are approximately constant at the task-relevant scale.
3. The time unit is confirmed.
4. Missing values and large gaps are resolved or explicitly modeled.
5. Trend and mean handling match the scientific question.
6. The target frequency is below Nyquist.

For a sample interval `dt` seconds:

- sample rate: `fs = 1 / dt`
- Nyquist frequency: `f_N = fs / 2`
- approximate frequency resolution: `df = 1 / duration`

A peak below Nyquist can still be an alias. Use domain knowledge or higher-rate data when aliasing is plausible.

## Irregular sampling

If sampling diagnostics report `sampling_regular=false`:

- Prefer Lomb-Scargle for stable sinusoidal periodicity.
- Preserve original timestamps.
- If resampling is unavoidable, state interpolation method and target rate.
- Re-run the analysis with at least one plausible alternative interpolation or parameter choice.
- Report sensitivity to gaps and the timestamp window.

## Preprocessing choices

- **Mean removal:** appropriate for oscillatory components; record it.
- **Detrending:** compare at least linear versus no detrending when trend is material.
- **Windowing:** useful for leakage in finite regular records; state the window.
- **Smoothing:** do not smooth before frequency analysis unless its transfer effect is understood.
- **Outliers:** investigate first; real transients may be the signal of interest.
- **Normalization:** preserve physical units in the final interpretation.

## Period claim checklist

Before reporting a period:

1. Confirm its unit.
2. Confirm at least three observed cycles; more are preferable.
3. Check that the frequency is safely below Nyquist.
4. Compare the candidate peak against nearby/background power.
5. Test sensitivity to detrending, windowing, or gap handling.
6. Check harmonics and subharmonics; the strongest peak may not be the fundamental.
7. Report uncertainty or a range instead of spurious precision.

## Anomaly checklist

- Define anomaly relative to a baseline and domain.
- Prefer median/MAD or quantile methods for heavy-tailed signals.
- Separate isolated spikes, level shifts, variance changes, and missing-data artifacts.
- Keep timestamps and original row identifiers for auditability.
- Do not remove an observation merely because a detector flags it.
