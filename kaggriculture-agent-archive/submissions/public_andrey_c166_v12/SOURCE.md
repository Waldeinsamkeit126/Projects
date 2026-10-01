# Public Andrey C166 V12 candidate

- Kaggle notebook: https://www.kaggle.com/code/andrewsokolovsky/kaggriculture-breaking-the-tie-2883-score?scriptVersionId=341994976
- Author: Andrey Naymushin (`andrewsokolovsky`)
- Historical version: V12 of 17
- Kaggle public score shown for V12: `2883.0`
- Strategy label in source: `C166 anti-H4 meta counter`
- Exact `main.py` bytes: `26585`
- Exact `main.py` SHA-256: `df4e899ad535754cf2ddbd3c16e48085916b0cd2baa5182a1a2cfc6a856abae5`
- Local `submission.tar.gz` bytes: `13913`
- Local `submission.tar.gz` SHA-256: `42b2006303354a85be1a4c751d1101ba4d0ff4db7a89dcb84de5e9b82cc097bc`

The source was extracted verbatim from the first rendered V12 notebook code cell by removing only the leading `%%writefile submission.py` magic line. Its byte count and SHA-256 exactly match the notebook's own build output. No strategy edits were applied.

The local archive contains exactly one top-level file, `main.py`. The file syntax-compiles successfully. A two-seat, one-seed runtime smoke test against the locally stored Indar agent completed successfully; both agents reached `DONE`, and the candidate's maximum measured action time was about `0.3 ms`. This local check is only a runtime/packaging sanity test, not a substitute for Kaggle leaderboard evaluation.
