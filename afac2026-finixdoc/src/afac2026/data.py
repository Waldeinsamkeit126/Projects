from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


def is_junk(path: Path) -> bool:
    return "__MACOSX" in path.parts or path.name.startswith("._") or path.name == ".DS_Store"


def files(root: Path, pattern: str) -> list[Path]:
    return sorted(p for p in root.rglob(pattern) if p.is_file() and not is_junk(p))


@dataclass(frozen=True)
class DatasetLayout:
    data_root: Path
    train_images: tuple[Path, ...]
    train_markdowns: tuple[Path, ...]
    test_images: tuple[Path, ...]
    submission_template: Path

    @classmethod
    def discover(cls, data_root: Path) -> "DatasetLayout":
        all_images = files(data_root, "*.jpg")
        all_mds = files(data_root, "*.md")
        md_by_stem = {p.stem: p for p in all_mds}
        train_images = tuple(p for p in all_images if p.stem in md_by_stem)
        test_images = tuple(p for p in all_images if p.stem not in md_by_stem)
        templates = [
            p
            for p in files(data_root, "*.csv")
            if p.name == "finix_ab_A_submit_mock.csv"
        ]
        if len(templates) != 1:
            raise RuntimeError(f"应当恰好找到一个提交模板，实际找到 {len(templates)} 个")
        layout = cls(
            data_root=data_root,
            train_images=train_images,
            train_markdowns=tuple(all_mds),
            test_images=test_images,
            submission_template=templates[0],
        )
        layout.validate()
        return layout

    def validate(self) -> None:
        image_stems = {p.stem for p in self.train_images}
        md_stems = {p.stem for p in self.train_markdowns}
        if image_stems != md_stems:
            raise RuntimeError(
                f"训练图片与GT不匹配: 缺GT={sorted(image_stems-md_stems)}, "
                f"缺图片={sorted(md_stems-image_stems)}"
            )
        with self.submission_template.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows or list(rows[0]) != ["file_name", "ground_truth"]:
            raise RuntimeError("提交模板列名或顺序不正确")
        template_names = {row["file_name"] for row in rows}
        test_names = {p.name for p in self.test_images}
        if template_names != test_names:
            raise RuntimeError("提交模板文件名与A榜图片不一致")

    def gt_for(self, image: Path) -> Path:
        matches = [p for p in self.train_markdowns if p.stem == image.stem]
        if len(matches) != 1:
            raise KeyError(image.name)
        return matches[0]
