"""Check report transcription, current links and unmodified release assets.

No dataset download, model fitting, RTL simulation or PPA measurement is run.
Only the Python standard library is required.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"!?\[([^\]]*(?:\][^)]*)?)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]*>", "", text)
    return re.sub(r"[\s#*`|]", "", text)


def main():
    manifest = json.loads((ROOT / "docs/report_source_manifest.json").read_text(encoding="utf8"))
    by_id = {e["id"]: e for e in manifest["body_items"]}
    for item in manifest["copied_source_files"] + manifest["original_vector_figures"]:
        assert digest(ROOT / item["path"]) == item["sha256"], item["path"]
    ratios = {}
    for name in manifest["active_report_documents"]:
        text = (ROOT / name).read_text(encoding="utf8")
        exact_chars = 0
        for match in re.finditer(r"<!-- report:p\d+:id(\d+) -->\n(.*?)(?=\n\n|\Z)", text, flags=re.S):
            item = by_id[int(match[1])]
            if item["kind"] != "paragraph" or item["text"].startswith("["):
                continue
            # Reference links retain the original [n] label.
            paragraph = re.sub(r"\[\[(\d+)\]\]\([^)]*\)", r"[\1]", match[2].rstrip())
            assert paragraph == item["text"], (name, item["id"])
            exact_chars += len(plain(paragraph))
        # Prose ratio: exclude tables, headings, captions, image/link-only lines,
        # reference entries and source markers; count navigation explanations.
        prose = []
        for line in text.splitlines():
            if not line or line.startswith(("#", "|", "![", "<!--", "<a ", "**", "[", ">")):
                continue
            prose.append(line)
        denominator = len(plain("\n".join(prose)))
        ratio = exact_chars / denominator if denominator else 1
        assert ratio >= .9, (name, ratio)
        ratios[name] = round(min(ratio, 1) * 100, 3)
    full = (ROOT / "reports/INTEGRATED_TECHNICAL_REPORT_KR.md").read_text(encoding="utf8")
    assert {int(v) for v in re.findall(r"<!-- report:p\d+:id(\d+) -->", full)} == set(by_id)
    for e in manifest["body_items"]:
        if e["kind"] == "table":
            with (ROOT / f'tables/report_2026/table-{e["number"]:02}.csv').open(encoding="utf8", newline="") as f:
                assert list(csv.reader(f)) == e["rows"]

    files = set(manifest["active_report_documents"])
    files.update(["REPRODUCIBILITY_KR.md", "START_HERE_KR.md", "WORKSPACE_INVENTORY_KR.md", "docs/README_KR.md", "docs/REPORT_SOURCE_KR.md", "docs/LEGACY_KR.md", "figures/FIGURE_INDEX.md"])
    for name in files:
        text = (ROOT / name).read_text(encoding="utf8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            path, _, anchor = unquote(target).partition("#")
            destination = (ROOT / name).parent / path
            assert destination.exists(), (name, target)
            if anchor:
                assert f'id="{anchor}"' in destination.read_text(encoding="utf8"), (name, target)

    base = ROOT / "models/rhythm3_duration/results_v3"
    model = json.loads((base / "frozen_model.json").read_text(encoding="utf8"))
    receipt = json.loads((base / "freeze_receipt.json").read_text(encoding="utf8"))
    assert digest(base / "frozen_model.json") == receipt["sha256"]
    assert model["class_order"] == ["NSR", "AF", "OTHER"]
    assert model["seconds"] == 1800 and model["snapshots"] == 30
    assert len(model["snapshot"]["spec"]) == len(model["final_spec"]) == 52
    assert digest(ROOT / "datasets/rhythm3_duration_v3/gold_labels.jsonl") == receipt["dataset_sha256"]
    rtl = ROOT / "design/digital/rtl/rhythm3_duration_v3"
    for source in (rtl / "sources.f").read_text().splitlines():
        assert (rtl / source).is_file(), source
    result = {"status": "PASS", "scope": "document_and_publication_integrity_only", "report_items": len(by_id), "tables": 13, "figures": 9, "equations": 2, "verbatim_prose_percent": ratios}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
