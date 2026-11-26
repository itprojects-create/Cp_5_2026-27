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

cp = CParser()
res = CParseResult()
fn_def = CFuncDef(name="goodG2B2", parameters=[], body="")

# Test each statement in body.children
for i, stmt in enumerate(body.children):
    sys.stdout.write(f"Statement {i}: {stmt.type} -> {_node_text(stmt)[:40]}...\n")
    sys.stdout.flush()
    cp._collect_calls(stmt, fn_def, res, False)
    sys.stdout.write(f"  Calls done, count={len(fn_def.calls)}\n")
    sys.stdout.flush()

print("All statements in body completed successfully!")
