import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import json
from External_scanner.interproc_graph_builder import InterprocGraphBuilder

manifest_path = BASE_DIR / "datasets" / "juliet_groups.json"
with open(manifest_path, encoding="utf-8") as f:
    groups = json.load(f)

print(f"Loaded {len(groups)} groups")
b = InterprocGraphBuilder()

for i in range(10):
    g = groups[i]
    gid = g["group_id"]
    print(f"Testing {i}: {gid}", flush=True)
    files = [
        str((BASE_DIR / file_path).resolve())
        if not Path(file_path).is_absolute()
        else file_path
        for file_path in g["files"]
    ]
    d = b.build_from_file_group(files, g["label"], gid, g["context"])
    print(f"  Done {i}: nodes={d.x.shape[0]} edges={d.edge_index.shape[1]}", flush=True)

print("Finished 10 successfully", flush=True)
