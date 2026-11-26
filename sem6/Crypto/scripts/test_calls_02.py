import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CParser, CParseResult, CFuncDef, _node_text, _node_line

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

tree = Parser(Language(tsc.language())).parse(code.encode('utf-8'))
child12 = tree.root_node.children[12]

# Find all call_expression nodes in child12
calls = []
def find_calls(node):
    if node.type == "call_expression":
        calls.append(node)
    for c in node.children:
        find_calls(c)

find_calls(child12)
print(f"Found {len(calls)} call_expression nodes in goodG2B2", flush=True)

cp = CParser()
res = CParseResult()
fn_def = CFuncDef(name="goodG2B2", parameters=[], body="")

for i, call_node in enumerate(calls):
    print(f"Call {i}: {_node_text(call_node)[:50]}...", flush=True)
    c = cp._extract_call(call_node, fn_def, res, False)
    if c:
        print(f"  -> Extracted: {c.callee_name}", flush=True)
    else:
        print(f"  -> Skipped/None", flush=True)

print("All calls extracted successfully!", flush=True)
