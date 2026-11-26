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
sub20 = stmt5.children[20]

cp = CParser()
res = CParseResult()
fn_def = CFuncDef(name="goodG2B2", parameters=[], body="")

print("Full text of sub20:")
print(_node_text(sub20))

# Trace calls in sub20
calls = []
def find_calls(n):
    if n.type == "call_expression":
        calls.append(n)
    for c in n.children:
        find_calls(c)

find_calls(sub20)
print(f"\nCalls in sub20: {len(calls)}")
for k, c in enumerate(calls):
    sys.stdout.write(f"Call {k}: {_node_text(c)[:30]}...\n")
    sys.stdout.flush()
    res_call = cp._extract_call(c, fn_def, res, False)
    sys.stdout.write(f"  Extracted: {res_call}\n")
    sys.stdout.flush()

print("Sub20 calls finished!")
