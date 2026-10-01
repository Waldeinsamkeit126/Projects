# Bounded restart approved 2026-09-25

The user explicitly confirmed a maximum of 26 additional calls, cumulative maximum 94. Retain and independently reconstruct the existing 688 answers from immutable model logs. Split failed PDF unit 68 into nine non-structure questions and one header-structure question. Then process units 69–89, followed by at most three grouped model repairs. No automatic retry; fatal network/HTTP/truncation/parsing failure stops all new calls. Each call caps output at 16,384 tokens.

Four mocked tests passed: split coverage/budget, dry-run and quota rejection, base plus bounded repairs, fatal truncation plus one-use authorization lock. A zero-call dry run passed. Frozen plan digest: `beebf28a3573a7c942c30986ef70d69a7aa1a9c24d30906299784b9c6c170b6f`.

The paid run was started once via the encrypted-credential launcher. Run identity and quota are in `restart-runs/authorization-94-total-20260925.started.json`. The old lock and old records are preserved. Do not restart this authorization or broaden limits without new approval. First new request (global 69) returned all nine ordinary answers with no local format failure, using 13,792 total tokens (276 output). Request 70 targets the header structure alone.

No new submission has occurred. The final run report, not this startup note, determines completion. Format validity and structural agreement do not imply ground-truth correctness or a score increase.

## Terminal outcome

Run `2026-09-25T03-28-15-719Z-53d112a3` completed all 23 base requests and 3 repairs. It consumed 26 new requests, exactly 94 cumulatively. No fatal error occurred. The failed PDF was successfully recovered by splitting: nine ordinary answers plus one header answer; header output used 1,872 tokens instead of the prior truncated 16,384.

All 908 IDs have records, with no missing IDs or detected cross-answer structural conflicts. 890 answers pass local validation; 18 remain invalid: nine empty responses and nine structures with overlapping/out-of-range cells. Repairs adopted eight answers. The report status is `needs-more-repair-no-export`, so no XLSX was exported or submitted and no further API calls are authorized.

Next option to present to the user: avoid further API expense and create an explicitly partial submission that preserves all 908 IDs, retains the 890 locally valid responses, keeps the nine original empty responses empty, and generically blanks the nine invalid structures. This changes the previously agreed strict all-valid export policy, so obtain the user's choice before doing so. Do not claim this will improve score. Alternative: seek a new bounded budget for structural repair, but do not silently spend more.

## Conservative export approved and completed

The user agreed to the conservative submission. Exported `submission-conservative-890-20260925.xlsx` in the restart run directory: 27,088 bytes, SHA256 `37a75d851149776909ef3248f1257ececcddb092d565322dca56b280a5e1ce38`. All 908 IDs preserved, 890 answers match model records exactly, 18 approved blank answers. No formulas or extra worksheets. Saved workbook reread verified; Excel blank cells import as null and are compared as empty only for equality, without modifying nonblank values. Official template formatting retained and preview inspected. The artifact marker was run once before authoring. Export API compatibility was fixed to documented `.save()`; the already-written workbook was subsequently verified without overwriting it.

The browser redirected from the submission page to Aliyun login. Login page is visible and marked for handoff. No upload or competition submission occurred. Next action after the user logs in: upload this exact verified file once, verify the new submission row, then read score/status. No further model calls or regenerated XLSX needed.

## 2026-09-26 upload attempt

Authenticated submission page verified with 5 remaining attempts, latest existing row still September 13 v47, and no duplicate conservative submission. XLSX SHA256 remains unchanged. The documented file-chooser flow timed out after clicking the upload button. A screenshot-grounded click and a page refresh followed by one further attempt also did not produce a chooser; no JavaScript dialog or changed submission row appeared. No file was selected or transmitted and no submission was confirmed. Browser tab retained and shown for user-assisted file selection. Screenshot: `development/upload-blocked-20260926.png`. Do not claim submission success or repeat blind clicks. Ask the user to manually open the chooser and select the exact verified file, then inspect the resulting state before any repeat upload.
