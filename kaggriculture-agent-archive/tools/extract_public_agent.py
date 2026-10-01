"""Safely extract a compressed public agent embedded in a Kaggle notebook."""

from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import re
import zlib
from pathlib import Path


def _assignment(module: ast.Module, name: str):
    for node in module.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            value = node.value
            return ast.literal_eval(value)
    raise KeyError(f"Missing notebook assignment: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    notebook = json.loads(args.notebook.read_text(encoding="utf-8"))
    code_sources = [
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
        if cell.get("cell_type") == "code"
    ]
    embedded = next(
        (
            source
            for source in code_sources
            if any(name in source for name in ("_AGENT_B85_PARTS", "_AGENT_B64_PARTS"))
        ),
        None,
    )
    if embedded is not None:
        module = ast.parse(embedded)
        try:
            parts = _assignment(module, "_AGENT_B85_PARTS")
            encoded = "".join(parts).encode("ascii")
            raw = zlib.decompress(base64.b85decode(encoded))
            encoding = "base85"
        except KeyError:
            parts = _assignment(module, "_AGENT_B64_PARTS")
            encoded = "".join(parts).encode("ascii")
            raw = zlib.decompress(base64.b64decode(encoded))
            encoding = "base64"
        expected_bytes = int(_assignment(module, "EXPECTED_MAIN_BYTES"))
        expected_sha256 = str(_assignment(module, "EXPECTED_MAIN_SHA256"))
    else:
        writefile = next(
            source
            for source in code_sources
            if source.lstrip().startswith("%%writefile main.py")
        )
        _magic, separator, payload = writefile.partition("\n")
        if not separator:
            raise ValueError("The %%writefile main.py cell has no payload")
        raw = payload.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        verification = "\n".join(code_sources)
        sha_match = re.search(r'expected_sha256\s*=\s*["\']([0-9a-f]{64})["\']', verification)
        bytes_match = re.search(r"assert\s+len\(agent_bytes\)\s*==\s*(\d+)", verification)
        if sha_match is None or bytes_match is None:
            raise ValueError("Missing writefile SHA-256 or byte-count assertion")
        expected_sha256 = sha_match.group(1)
        expected_bytes = int(bytes_match.group(1))
        encoding = "writefile"

    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if len(raw) != expected_bytes:
        raise ValueError(f"Length mismatch: {len(raw)} != {expected_bytes}")
    if actual_sha256 != expected_sha256:
        raise ValueError(f"SHA-256 mismatch: {actual_sha256} != {expected_sha256}")
    compile(raw, str(args.output), "exec")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "bytes": len(raw),
                "sha256": actual_sha256,
                "encoding": encoding,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
