"""
audit_juliet.py: Discovers and groups Juliet test files into interprocedural test groups,
splitting each group into balanced vulnerable and clean graph pairs.

A "group" = all .c files sharing the same base prefix (e.g. _54a.c, _54b.c, ... _54e.c)
within the same CWE directory.

Each Juliet group produces TWO entries:
1. <group_id>__bad  (label=1, context='bad')
2. <group_id>__good (label=0, context='good')

Manual test cases (datasets/manual_tests/) and Day5 test cases (Day5_test/)
are included in the 'test' split.

Output: datasets/juliet_groups.json
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# CWEs to include and their split assignment
CWE_SPLITS = {
    "CWE321_Hard_Coded_Cryptographic_Key": "train",
    "CWE327_Use_Broken_Crypto": "train",
    "CWE338_Weak_PRNG": "train",
    "CWE256_Plaintext_Storage_of_Password": "val",
    "CWE259_Hard_Coded_Password": "val",
}

TESTCASES_DIR = BASE / "datasets" / "juliet" / "testcases"
MANUAL_DIR = BASE / "datasets" / "manual_tests"
DAY5_DIR = BASE / "Day5_test"


def manifest_path(path: Path) -> str:
    """Return a path that is portable across clones of the repository."""
    return path.relative_to(BASE).as_posix()


def strip_guards(code: str) -> str:
    """Remove #ifndef OMITBAD / #ifdef OMITBAD / #endif guards."""
    code = re.sub(r"#ifndef\s+OMIT\w+\r?\n", "", code)
    code = re.sub(r"#ifdef\s+OMIT\w+\r?\n", "", code)
    code = re.sub(r"#endif(?:\s+/\*[^*]*\*/)?\r?\n", "\n", code)
    return code


def group_files_by_prefix(cwe_dir: Path):
    """
    Groups .c files in a CWE directory by their test case prefix.
    Multi-file testcases (ending in e.g. 54a.c, 54b.c) share the same prefix (e.g. ...54).
    Single-file testcases (e.g. ...01.c) form their own single-file group.
    """
    groups = defaultdict(list)
    for f in sorted(cwe_dir.rglob("*.c")):
        m = re.match(r"^(.*_\d+)[a-e]\.c$", f.name, re.IGNORECASE)
        if m:
            group_key = m.group(1)
        else:
            group_key = f.stem
        groups[group_key].append(manifest_path(f))
    return groups


def build_juliet_groups(cwe_name: str, split: str) -> list:
    """
    Builds balanced group pairs (bad & good) for a CWE.
    """
    cwe_dir = TESTCASES_DIR / cwe_name
    if not cwe_dir.exists():
        print(f"  [SKIP] {cwe_name} — directory not found", file=sys.stderr)
        return []

    prefix_groups = group_files_by_prefix(cwe_dir)
    cwe_code = cwe_name.split("_")[0]
    groups = []

    for group_key, file_paths in sorted(prefix_groups.items()):
        # Vulnerable variant
        groups.append(
            {
                "group_id": f"{group_key}__bad",
                "base_group": group_key,
                "cwe": cwe_code,
                "split": split,
                "label": 1,
                "context": "bad",
                "files": file_paths,
                "n_files": len(file_paths),
            }
        )
        # Clean variant
        groups.append(
            {
                "group_id": f"{group_key}__good",
                "base_group": group_key,
                "cwe": cwe_code,
                "split": split,
                "label": 0,
                "context": "good",
                "files": file_paths,
                "n_files": len(file_paths),
            }
        )
    return groups


def add_manual_and_day5(groups: list):
    """Add hand-labeled test cases from manual_tests/ and Day5_test/."""
    # manual_tests (clean_near_misses, macro_variants, mixed, pointer_alias, wrapper_variants)
    if MANUAL_DIR.exists():
        for f in sorted(MANUAL_DIR.rglob("*.c")):
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            header = lines[0] if lines else ""
            if "CLEAN" in header:
                label = 0
            elif "VULNERABLE" in header:
                label = 1
            else:
                label = (
                    1
                    if re.search(
                        r"hardcoded|secret|RAW_KEY",
                        f.read_text(encoding="utf-8", errors="ignore"),
                        re.I,
                    )
                    else 0
                )

            groups.append(
                {
                    "group_id": f"manual__{f.parent.name}__{f.stem}",
                    "base_group": f"manual__{f.parent.name}__{f.stem}",
                    "cwe": "CWE321",
                    "split": "test",
                    "label": label,
                    "context": "full",
                    "files": [manifest_path(f)],
                    "n_files": 1,
                }
            )

    # Day5_test (real OpenSSL API cases)
    if DAY5_DIR.exists():
        # Day5 known ground-truth labels
        day5_labels = {
            "direct_real_api": 1,
            "macro_real_api": 1,
            "wrapper_real_api": 1,
            "logging_only_real": 0,
            "runtime_real_api": 0,
        }
        for f in sorted(DAY5_DIR.rglob("*.c")):
            stem = f.stem
            label = day5_labels.get(
                stem,
                1
                if "real_api" in stem
                and "logging" not in stem
                and "runtime" not in stem
                else 0,
            )
            groups.append(
                {
                    "group_id": f"day5__{stem}",
                    "base_group": f"day5__{stem}",
                    "cwe": "CWE321",
                    "split": "test",
                    "label": label,
                    "context": "full",
                    "files": [manifest_path(f)],
                    "n_files": 1,
                }
            )


def main():
    all_groups = []

    print("=== Juliet Dataset Audit & Grouping ===\n")
    for cwe_name, split in CWE_SPLITS.items():
        groups = build_juliet_groups(cwe_name, split)
        vuln = sum(1 for g in groups if g["label"] == 1)
        clean = sum(1 for g in groups if g["label"] == 0)
        multi = sum(1 for g in groups if g["n_files"] > 1)
        print(f"{cwe_name}")
        print(
            f"  Graphs: {len(groups)} (vuln={vuln}, clean={clean}, multi-file={multi}), split={split}"
        )
        all_groups.extend(groups)

    print()
    print("=== Manual + Day5 Test Cases ===")
    before = len(all_groups)
    add_manual_and_day5(all_groups)
    added = len(all_groups) - before
    test_groups = [g for g in all_groups if g["split"] == "test"]
    test_vuln = sum(1 for g in test_groups if g["label"] == 1)
    test_clean = sum(1 for g in test_groups if g["label"] == 0)
    print(f"  Added {added} test graphs (vuln={test_vuln}, clean={test_clean})")

    # Summary
    print("\n=== Dataset Summary ===")
    splits = {"train": 0, "val": 0, "test": 0}
    labels = {"vuln": 0, "clean": 0}
    per_split_labels = defaultdict(lambda: {"vuln": 0, "clean": 0})

    for g in all_groups:
        sp = g["split"]
        lb = "vuln" if g["label"] == 1 else "clean"
        splits[sp] = splits.get(sp, 0) + 1
        labels[lb] += 1
        per_split_labels[sp][lb] += 1

    print(f"  Total graphs : {len(all_groups)}")
    for sp in ["train", "val", "test"]:
        vl = per_split_labels[sp]["vuln"]
        cl = per_split_labels[sp]["clean"]
        pct = (vl / (vl + cl) * 100) if (vl + cl) > 0 else 0
        print(
            f"  {sp:<12s}: {splits.get(sp, 0):3d} graphs (vuln={vl:3d}, clean={cl:3d}, {pct:.1f}% vuln)"
        )

    # Save
    out = BASE / "datasets" / "juliet_groups.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(all_groups, f, indent=2)
    print(f"\n  Saved manifest: {out}")
    return all_groups


if __name__ == "__main__":
    main()
