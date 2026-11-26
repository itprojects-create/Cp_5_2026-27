import sys
from pathlib import Path
BASE_DIR = Path.cwd()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import re
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CParser, CParseResult, CFuncDef, _node_text, _node_line

try:
    fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
    code = fp.read_text(encoding='utf-8', errors='ignore')
    code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
    code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
    code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

    tree = Parser(Language(tsc.language())).parse(code.encode('utf-8'))
    child12 = tree.root_node.children[12]

    cp = CParser()
    res = CParseResult()
    body_node = child12.child_by_field_name("body")
    fn_def = CFuncDef(name="goodG2B2", parameters=[], body=_node_text(body_node), line_number=_node_line(child12))

    print("Step 1: _collect_calls...", flush=True)
    cp._collect_calls(body_node, fn_def, res, skip_first_call=True)
    print(f"  Calls found: {len(fn_def.calls)}", flush=True)

    print("Step 2: _collect_statements...", flush=True)
    cp._collect_statements(body_node, res)
    print(f"  Assignments found: {len(res.assignments)}", flush=True)
except BaseException as e:
    import traceback
    traceback.print_exc()
