import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from External_scanner.semantic_engine import SemanticEngine
from External_scanner.interproc_graph_builder import strip_guards

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = strip_guards(fp.read_text(encoding='utf-8', errors='ignore'))
se = SemanticEngine()

print("Testing Stage 1: macro_expander...", flush=True)
expanded = se.macro_expander.expand(code)
print("Stage 1 done.", flush=True)

print("Testing Stage 2: wrapper_resolver...", flush=True)
functions = se.wrapper_resolver.extract_functions(expanded, "02.c")
wrappers = se.wrapper_resolver.find_wrappers(functions)
print(f"Stage 2 done. Functions: {len(functions)}, Wrappers: {len(wrappers)}", flush=True)

print("Testing Stage 3: alias_analyzer...", flush=True)
se.alias_analyzer.parse_pointer_assignments(expanded)
se.alias_analyzer.find_pointer_assignments(expanded)
alias_groups = se.alias_analyzer.build_alias_sets()
print(f"Stage 3 done. Alias groups: {len(alias_groups)}", flush=True)

print("Testing Stage 4: flow_tracker...", flush=True)
se._extract_assignments(expanded, "02.c")
print(f"Stage 4 extract assignments done.", flush=True)
findings = se._detect_crypto_misuse(expanded, functions, wrappers, "02.c")
print(f"Stage 4 detect done. Findings: {len(findings)}", flush=True)

node_dicts, edge_dicts = se._serialize_graph(functions, wrappers, findings, "02.c")
print(f"Stage 4 serialize done. Nodes: {len(node_dicts)}, Edges: {len(edge_dicts)}", flush=True)

print("ALL STAGES COMPLETED SUCCESSFULLY!", flush=True)
