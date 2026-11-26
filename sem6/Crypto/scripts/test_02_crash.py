import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
from External_scanner.c_parser import CParser
from External_scanner.semantic_engine import SemanticEngine
from External_scanner.interproc_graph_builder import strip_guards

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code_raw = fp.read_text(encoding='utf-8', errors='ignore')
print("Read code", flush=True)

code_clean = strip_guards(code_raw)
print("Stripped guards", flush=True)

parser = CParser()
print("Parsing with CParser...", flush=True)
c_res = parser.parse(code_clean)
print(f"CParser done: {len(c_res.functions)} functions", flush=True)

engine = SemanticEngine()
print("Analyzing with SemanticEngine...", flush=True)
sem_res = engine.analyze(code_clean, file_path=fp.name)
print("SemanticEngine done", flush=True)
