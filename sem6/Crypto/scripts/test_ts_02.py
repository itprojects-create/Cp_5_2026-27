import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CParser, CParseResult

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

p = Parser(Language(tsc.language()))
tree = p.parse(code.encode('utf-8'))

cp = CParser()
res = CParseResult()

for i, child in enumerate(tree.root_node.children):
    if child.type == "function_definition":
        print(f"Extracting function {i}...", flush=True)
        cp._extract_function(child, res)
        print(f"  Done function {i}: {res.functions[-1].name}", flush=True)

print("Finished all functions!", flush=True)
