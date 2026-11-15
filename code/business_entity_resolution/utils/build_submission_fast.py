"""Fast high-precision submission generator for ML Challenge 2026.
Generates compliant matching_results.tsv and candidate_pairs.tsv in <2 minutes.
"""
import csv
import os
import re
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "dataset" / "test"
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUFFIX_RE = re.compile(r"\b(inc|corp|corporation|llc|ltd|limited|pvt|private|sa|sarl|gmbh|co|company|group|holding)\b", re.IGNORECASE)
CLEAN_RE = re.compile(r"[^a-zA-Z0-9\s]")


def clean_core_name(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = CLEAN_RE.sub(" ", s)
    s = SUFFIX_RE.sub(" ", s)
    return " ".join(s.split())


def main():
    t0 = time.time()
    print("[1/5] Loading test_source1.tsv...")
    s1_ids = []
    name_to_s1 = defaultdict(list)
    s1_matches = defaultdict(list)
    s1_cands = defaultdict(list)

    s1_file = DATA_DIR / "test_source1.tsv"
    with open(s1_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sid = row["entity_id"]
            s1_ids.append(sid)
            name = clean_core_name(row["business_name"])
            country = row["country"].strip()
            if name:
                name_to_s1[(country, name)].append(sid)

    print(f"Loaded {len(s1_ids):,} Source 1 entities ({time.time()-t0:.1f}s)")

    # Scan test_source2 and test_source3
    for s_idx in (2, 3):
        t_start = time.time()
        pool_file = DATA_DIR / f"test_source{s_idx}.tsv"
        print(f"[2/5] Streaming Source {s_idx} from {pool_file.name}...")
        matched_count = 0
        with open(pool_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                target_id = row["entity_id"]
                country = row["country"].strip()
                name = clean_core_name(row["business_name"])
                if not name:
                    continue
                k = (country, name)
                if k in name_to_s1:
                    for sid in name_to_s1[k]:
                        if len(s1_matches[sid]) < 8:
                            s1_matches[sid].append(target_id)
                        if len(s1_cands[sid]) < 10:
                            s1_cands[sid].append(target_id)
                        matched_count += 1
        print(f"Source {s_idx} finished in {time.time()-t_start:.1f}s ({matched_count:,} matches linked)")

    print("[3/5] Writing output files...")
    matching_path = OUT_DIR / "matching_results.tsv"
    candidate_path = OUT_DIR / "candidate_pairs.tsv"

    with open(matching_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("source1_entity_id\tmatched_entity_ids\n")
        for sid in s1_ids:
            ms = s1_matches.get(sid, [])
            f.write(f"{sid}\t{','.join(dict.fromkeys(ms))}\n")

    with open(candidate_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("source1_entity_id\tcandidate_entity_ids\n")
        for sid in s1_ids:
            cs = s1_cands.get(sid, [])
            f.write(f"{sid}\t{','.join(dict.fromkeys(cs))}\n")

    print(f"Saved: {matching_path}")
    print(f"Saved: {candidate_path}")

    print("[4/5] Running official validation...")
    validator = ROOT / "utils" / "validate_submission.py"
    cmd = f'python "{validator}" --matching "{matching_path}" --candidate "{candidate_path}" --test-dir "{DATA_DIR}"'
    rc = os.system(cmd)
    if rc != 0:
        print("WARNING: Validator returned non-zero code!")
    else:
        print(">>> VALIDATION PASSED SUCCESSFULLY! <<<")

    print("[5/5] Packaging ZARA_submission.zip...")
    zip_path = ROOT / "ZARA_submission.zip"
    code_dir = ROOT / "code" / "business_entity_resolution"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(matching_path, "output/matching_results.tsv")
        z.write(candidate_path, "output/candidate_pairs.tsv")
        for p in sorted(code_dir.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".zip", ".log"):
                z.write(p, "code/business_entity_resolution/" + p.relative_to(code_dir).as_posix())
        doc_path = ROOT / "Documentation_template.md"
        if doc_path.exists():
            z.write(doc_path, "Documentation_template.md")

    print(f"\nALL DONE in {time.time()-t0:.1f}s!")
    print(f"READY FOR LEADERBOARD: {matching_path}")
    print(f"ZIP PACKAGE: {zip_path}")


if __name__ == "__main__":
    main()
