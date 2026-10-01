# Biohub - Cell Tracking During Development

Local competition artifacts archived at the owner's request. This is a historical archive, not a promise of a reproducible final Kaggle run. Later notebooks run only on Kaggle may not be present locally. Third-party files retain their original licenses.

The payload is content-deduplicated. Concatenate payload.zip.part* in lexical order into payload.zip. Verify its SHA256 against archive-info.json, then extract it. Each extracted filename is its SHA256. Use manifest.json to copy each hash-named file to its ArchivePath (relative to a fresh restore directory). Identical source files share one stored payload. Absolute machine paths are intentionally omitted.

Unidentified files, credentials, unrelated competitions, and browser-only data were not collected. Local cleanup happens only after a fresh remote clone and verification of every stored file.
