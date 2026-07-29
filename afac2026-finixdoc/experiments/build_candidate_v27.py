from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from afac2026.config import Settings  # noqa: E402
from afac2026.data import DatasetLayout  # noqa: E402
from afac2026.submission import write_submission  # noqa: E402
from build_candidate_v24 import load_submission, parse_tables  # noqa: E402


BASE_SHA256 = "2d307aedb4021b06a9bdc0bc89428c77484862f608f1886623044543c0b7b5da"

TARGET_41C = "41c420f9-5026-43c6-8ae6-caf4c60adee6.jpg"
TARGET_8154 = "8154f223-bf21-4d41-b729-cea88fd4fd4e.jpg"


def table_shapes(markdown: str) -> list[list[int]]:
    return [
        [len(table.cell_text_rows), len(table.cell_text_rows[0])]
        for table in parse_tables(markdown)
    ]


def replace_once(markdown: str, old: str, new: str, target: str) -> str:
    count = markdown.count(old)
    if count != 1:
        raise ValueError(f"{target}: expected one repair anchor, found {count}")
    return markdown.replace(old, new, 1)


def repair_41c(markdown: str) -> str:
    row_28_9 = (
        "<tr><td>5</td><td>10</td><td>28</td><td>男</td>"
        "<td>9</td><td>5416.96</td></tr>"
    )
    row_29_1 = (
        "<tr><td>5</td><td>10</td><td>29</td><td>男</td>"
        "<td>1</td><td>673.29</td></tr>"
    )
    row_28_10 = (
        "<tr><td>5</td><td>10</td><td>28</td><td>男</td>"
        "<td>10</td><td>0</td></tr>"
    )
    return replace_once(
        markdown,
        row_28_9 + "\n" + row_29_1,
        row_28_9 + "\n" + row_28_10 + "\n" + row_29_1,
        TARGET_41C,
    )


def repair_8154(markdown: str) -> str:
    row_32_9 = (
        "<tr><td>5</td><td>10</td><td>32</td><td>男</td>"
        "<td>9</td><td>5410.88</td></tr>"
    )
    wrong_row_33_1 = (
        "<tr><td>5</td><td>10</td><td>33</td><td>男</td>"
        "<td>1</td><td>0</td></tr>"
    )
    row_32_10 = (
        "<tr><td>5</td><td>10</td><td>32</td><td>男</td>"
        "<td>10</td><td>0</td></tr>"
    )
    row_33_1 = (
        "<tr><td>5</td><td>10</td><td>33</td><td>男</td>"
        "<td>1</td><td>673.27</td></tr>"
    )
    return replace_once(
        markdown,
        row_32_9 + "\n" + wrong_row_33_1,
        row_32_9 + "\n" + row_32_10 + "\n" + row_33_1,
        TARGET_8154,
    )


def assert_rows(markdown: str, expected: dict[tuple[str, str], str]) -> None:
    rows = [row for table in parse_tables(markdown) for row in table.cell_text_rows]
    indexed = {(row[2], row[4]): row[5] for row in rows if len(row) == 6}
    for key, value in expected.items():
        if indexed.get(key) != value:
            raise ValueError(f"row validation failed for {key}: {indexed.get(key)!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("D:/AFAC2026/outputs/afac_A_submission_v26.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "work_afac_A_submission_v27.csv"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "work_afac_A_submission_v27.report.json",
    )
    parser.add_argument(
        "--candidate-dir", type=Path, default=ROOT / "work_v27"
    )
    args = parser.parse_args()

    base_sha256 = hashlib.sha256(args.base.read_bytes()).hexdigest()
    if base_sha256 != BASE_SHA256:
        raise ValueError(f"v26 base hash changed: {base_sha256}")

    settings = Settings.load(ROOT)
    data = DatasetLayout.discover(settings.data_root)
    base = load_submission(args.base)
    old_shapes = {
        TARGET_41C: table_shapes(base[TARGET_41C]),
        TARGET_8154: table_shapes(base[TARGET_8154]),
    }
    if old_shapes != {
        TARGET_41C: [[77, 6], [76, 6]],
        TARGET_8154: [[77, 6], [76, 6]],
    }:
        raise ValueError(f"base table shapes changed: {old_shapes}")

    repaired = {
        TARGET_41C: repair_41c(base[TARGET_41C]),
        TARGET_8154: repair_8154(base[TARGET_8154]),
    }
    new_shapes = {name: table_shapes(value) for name, value in repaired.items()}
    expected_shapes = {
        TARGET_41C: [[77, 6], [77, 6]],
        TARGET_8154: [[77, 6], [77, 6]],
    }
    if new_shapes != expected_shapes:
        raise ValueError(f"candidate table shapes wrong: {new_shapes}")

    assert_rows(
        repaired[TARGET_41C],
        {("28", "9"): "5416.96", ("28", "10"): "0", ("29", "1"): "673.29"},
    )
    assert_rows(
        repaired[TARGET_8154],
        {("32", "9"): "5410.88", ("32", "10"): "0", ("33", "1"): "673.27"},
    )

    args.candidate_dir.mkdir(parents=True, exist_ok=True)
    for name, markdown in repaired.items():
        (args.candidate_dir / f"{Path(name).stem}.md").write_text(
            markdown + "\n", encoding="utf-8"
        )

    predictions = dict(base)
    predictions.update(repaired)
    write_submission(data.submission_template, predictions, args.output)
    written = load_submission(args.output)
    changed = sorted(name for name in written if written[name] != base[name])
    expected_changed = sorted(repaired)
    if changed != expected_changed:
        raise ValueError(f"changed samples wrong: {changed}")
    if len(written) != 100 or len(set(written)) != 100:
        raise ValueError("submission row/filename count changed")
    blanks = sorted(name for name, value in written.items() if not value.strip())
    if blanks:
        raise ValueError(f"blank predictions: {blanks}")
    for name in repaired:
        if written[name] != repaired[name]:
            raise ValueError(f"round-trip changed candidate markdown: {name}")

    report = {
        "base": str(args.base),
        "base_sha256": base_sha256,
        "output": str(args.output),
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "rows": len(written),
        "unique_file_names": len(set(written)),
        "blank_predictions": len(blanks),
        "changed_samples": len(changed),
        "changed_names": changed,
        "repairs": [
            {
                "file_name": TARGET_41C,
                "old_shapes": old_shapes[TARGET_41C],
                "new_shapes": new_shapes[TARGET_41C],
                "inserted_row": ["5", "10", "28", "男", "10", "0"],
                "source_evidence": "work_v25/41c_right_bottom.jpg",
            },
            {
                "file_name": TARGET_8154,
                "old_shapes": old_shapes[TARGET_8154],
                "new_shapes": new_shapes[TARGET_8154],
                "inserted_row": ["5", "10", "32", "男", "10", "0"],
                "corrected_row": {
                    "key": ["5", "10", "33", "男", "1"],
                    "old_value": "0",
                    "new_value": "673.27",
                },
                "source_evidence": "work_v25/8154_group32_33.jpg",
            },
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
