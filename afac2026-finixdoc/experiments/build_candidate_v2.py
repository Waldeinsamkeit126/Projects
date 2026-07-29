from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.normalize import normalized_for_alignment  # noqa: E402
from afac2026.score import diagnose  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402


RESTORE_COMPLETE_API = {
    "41c420f9-5026-43c6-8ae6-caf4c60adee6.jpg",
    "8154f223-bf21-4d41-b729-cea88fd4fd4e.jpg",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def family(path: Path) -> str:
    return "table" if any("table" in part.lower() for part in path.parts) else "long"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v2.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v2.report.json"),
    )
    args = parser.parse_args()
    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    gt_by_stem = {path.stem: path for path in data.train_markdowns}
    train_by_key: defaultdict[tuple[str, str], list[Path]] = defaultdict(list)
    for image in data.train_images:
        train_by_key[(family(image), sha256_file(image))].append(image)

    prediction_dir = settings.output_dir / "predictions_A"
    predictions: dict[str, str] = {}
    overrides: list[dict[str, object]] = []
    for image in data.test_images:
        current_path = prediction_dir / f"{image.stem}.md"
        current = current_path.read_text(encoding="utf-8")
        selected = current
        source = "v1_prediction"
        candidates = train_by_key.get((family(image), sha256_file(image)), [])
        if candidates:
            ground_truths = [
                gt_by_stem[candidate.stem].read_text(encoding="utf-8")
                for candidate in candidates
            ]
            normalized = {normalized_for_alignment(value) for value in ground_truths}
            if len(normalized) == 1:
                selected = ground_truths[0]
                source = f"exact_train_duplicate:{candidates[0].name}"
                diagnostic = diagnose(current, selected)
                overrides.append(
                    {
                        "file_name": image.name,
                        "source": source,
                        "old_chars": len(current),
                        "new_chars": len(selected),
                        "old_vs_exact_gt": diagnostic.to_dict(),
                    }
                )
        if image.name in RESTORE_COMPLETE_API:
            backup = (
                settings.output_dir
                / "repair_backups"
                / image.stem
                / f"{image.stem}.md"
            )
            selected = backup.read_text(encoding="utf-8")
            source = "complete_api_backup"
            overrides.append(
                {
                    "file_name": image.name,
                    "source": source,
                    "old_chars": len(current),
                    "new_chars": len(selected),
                }
            )
        predictions[image.name] = selected

    write_submission(data.submission_template, predictions, args.output)
    report = {
        "output": str(args.output),
        "rows": len(predictions),
        "overrides": overrides,
        "exact_duplicate_overrides": sum(
            str(item["source"]).startswith("exact_train_duplicate")
            for item in overrides
        ),
        "api_restore_overrides": sum(
            item["source"] == "complete_api_backup" for item in overrides
        ),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.report.with_suffix(args.report.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(args.report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
