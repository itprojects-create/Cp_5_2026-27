import sys
from pathlib import Path
BASE_DIR = Path.cwd()
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
body_node = child12.child_by_field_name("body")

cp = CParser()
res = CParseResult()
fn_def = CFuncDef(name="goodG2B2", parameters=[], body="")

step = 0
def debug_collect_calls(node, depth=0):
    global step
    if node is None:
        return
    step += 1
    sys.stdout.write(f"[{step:3d}] depth={depth} type={node.type}: {_node_text(node)[:30]}\n")
    sys.stdout.flush()

    if node.type == "call_expression":
        call = cp._extract_call(node, fn_def, res, False)
        sys.stdout.write(f"     -> extract_call returned: {call}\n")
        sys.stdout.flush()
        if call is not None:
            return

    for c in node.children:
        debug_collect_calls(c, depth + 1)

debug_collect_calls(body_node)
print("Finished without crash!", flush=True)
