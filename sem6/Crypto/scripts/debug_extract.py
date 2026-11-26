import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CParser, CParseResult, CFuncDef, _node_text, _node_line, CONTROL_KEYWORDS

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

tree = Parser(Language(tsc.language())).parse(code.encode('utf-8'))
node = tree.root_node.children[12]

cp = CParser()
result = CParseResult()

print("Line 1: type_text...", flush=True)
type_text = _node_text(node.child_by_field_name("type"))
print(f"  type_text = {type_text}", flush=True)

print("Line 2: declarator...", flush=True)
declarator = node.child_by_field_name("declarator")

def find_identifier(n):
    if n is None:
        return ""
    if n.type == "identifier":
        return _node_text(n)
    for c in n.named_children:
        r = find_identifier(c)
        if r:
            return r
    return ""

fn_name = find_identifier(declarator)
print(f"  fn_name = {fn_name}", flush=True)

print("Line 3: params...", flush=True)
params = []
func_decl = declarator
if func_decl is not None:
    for child in func_decl.named_children:
        if child.type == "parameter_list":
            for param in child.named_children:
                if param.type == "parameter_declaration":
                    pname = cp._parameter_name(param)
                    if pname:
                        params.append(pname)
print(f"  params = {params}", flush=True)

print("Line 4: body...", flush=True)
body_node = node.child_by_field_name("body")
body = _node_text(body_node)
is_static = "static" in type_text
print(f"  is_static = {is_static}", flush=True)

print("Line 5: CFuncDef...", flush=True)
fn_def = CFuncDef(
    name=fn_name,
    parameters=params,
    body=body,
    line_number=_node_line(node),
    return_type=type_text.strip() or "void",
    is_static=is_static,
)
print("  fn_def created", flush=True)

print("Line 6: _collect_calls...", flush=True)
cp._collect_calls(body_node, fn_def, result, skip_first_call=True)
print(f"  Calls: {len(fn_def.calls)}", flush=True)

print("Line 7: _collect_statements...", flush=True)
cp._collect_statements(body_node, result)
print(f"  Assignments: {len(result.assignments)}", flush=True)

print("Line 8: append to result.functions...", flush=True)
result.functions.append(fn_def)
print("ALL DONE!", flush=True)
