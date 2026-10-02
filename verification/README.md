# Refactor Verification

Artifacts proving the detector refactor is behavior-preserving and that
the AST cache behaves across runs.

## Inputs

- `../samples/OrderProcessorSample.java` - Java sample that triggers all
  four detectors (37 findings on the pre-refactor build).
- `../samples/OrderProcessorSample_edited.java` - same sample with one
  field removed (`private boolean flag5;`). This removes the God Class
  finding and shifts later line numbers by one.

## Scripts

- `baseline_before_refactor.py` - regenerates
  `baseline_before_refactor.json` (37 legacy issue dicts + metrics) using
  the pre-refactor engine. The checked-in JSON was captured on the
  original code (git HEAD) before refactoring.
- `verify_refactor.py` - asserts:
  1. Refactored legacy issue output (Type/Target/Severity/Reason/Category)
     is identical, in the same order, to the baseline; metrics identical.
  2. Two runs on the unchanged sample return identical order/content.
  3. Cold run cache stats = 0 hits / 1 miss; warm run = 1 hit / 0 miss.
  4. Edited content run = 0 hits / 1 miss and conclusions change
     (God Class disappears; Design findings 7 -> 6).
  5. A different file never aliases the cache; original content still
     hits afterwards (content-addressed, no cross-file bleed).
  6. Catalog order equals registry registration order and partial config
     flags show the correct ON/OFF state.
  7. Every `Finding` carries file, 1-based line and severity.

Run:

```powershell
python verification/verify_refactor.py
```

## Screenshots (recordings of the running Streamlit app)

- `screenshots/00_cold_run_executive.png` - first analysis: Executive
  Dashboard (37 issues, 2 Critical, Quality 6/100) and code metrics.
- `screenshots/01_cold_run_hits0.png` - Detector Catalog, cold run:
  AST Cache Hits 0, Misses 1, 4/4 detectors, Design 7 findings incl.
  God Class.
- `screenshots/02_warm_run_hits1.png` - second analysis of the same
  unchanged content: Hits 1, Misses 0; every entry identical.
- `screenshots/03_edited_run_hits0_changed.png` - edited sample:
  Hits reset to 0, Misses 1; Design drops to 6, God Class gone,
  line numbers shift by one.
