import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CParser, CParseResult, CFuncDef, _node_text, _node_line, _is_in_call_args

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

def find_first_call(n):
    if n.type == "call_expression":
        return n
    for c in n.children:
        r = find_first_call(c)
        if r:
            return r
    return None

cnode = find_first_call(sub20)
print("Found cnode:", _node_text(cnode)[:40], flush=True)

print("Step 1: _is_in_call_args...", flush=True)
in_args = _is_in_call_args(cnode)
print(f"  in_args = {in_args}", flush=True)

cp = CParser()
print("Step 2: func_node & callee...", flush=True)
func_node = cnode.child_by_field_name("function")
callee = cp._callee_name(func_node)
print(f"  callee = {callee}", flush=True)

print("Step 3: arguments...", flush=True)
arg_list = cnode.child_by_field_name("arguments")
for idx, arg in enumerate(arg_list.named_children):
    print(f"  arg {idx}: {_node_text(arg)}", flush=True)

print("Step 4: parent check...", flush=True)
parent = getattr(cnode, "parent", None)
print(f"  parent type = {parent.type if parent else None}", flush=True)

print("Step 5: _node_line...", flush=True)
line = _node_line(cnode)
print(f"  line = {line}", flush=True)

print("ALL STEPS COMPLETED!", flush=True)
