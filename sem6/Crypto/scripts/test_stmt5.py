import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
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
body = child12.child_by_field_name("body")
stmt5 = body.children[5]

cp = CParser()
res = CParseResult()
fn_def = CFuncDef(name="goodG2B2", parameters=[], body="")

for j, sub in enumerate(stmt5.children):
    sys.stdout.write(f"Sub-statement {j}: {sub.type} -> {_node_text(sub)[:40]}...\n")
    sys.stdout.flush()
    cp._collect_calls(sub, fn_def, res, False)
    sys.stdout.write(f"  Done, calls={len(fn_def.calls)}\n")
    sys.stdout.flush()

print("All sub-statements in stmt5 completed successfully!")
