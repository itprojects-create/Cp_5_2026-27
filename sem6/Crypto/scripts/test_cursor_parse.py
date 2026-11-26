import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import tree_sitter_c as tsc
from tree_sitter import Language, Parser
from External_scanner.c_parser import CCall, CAssignment, CFuncDef, CParseResult, CONTROL_KEYWORDS

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

source_bytes = code.encode('utf-8')
tree = Parser(Language(tsc.language())).parse(source_bytes)
root = tree.root_node

def safe_text(n):
    if n is None: return ""
    try: return n.text.decode('utf-8', 'replace').strip()
    except Exception: return ""

def parse_with_cursor(root):
    result = CParseResult()
    for child in root.children:
        if child.type == "function_definition":
            cursor = child.walk()
            fn_name = ""
            # find identifier in declarator
            dec = child.child_by_field_name("declarator")
            while dec and dec.type != "identifier":
                dec = dec.child_by_field_name("declarator") or (dec.named_children[0] if dec.named_children else None)
            if dec:
                fn_name = safe_text(dec)
            if not fn_name or fn_name in CONTROL_KEYWORDS:
                continue

            body_node = child.child_by_field_name("body")
            fn_def = CFuncDef(name=fn_name, parameters=[], body=safe_text(body_node), line_number=child.start_point[0]+1)

            # Traverse body with TreeCursor
            b_cursor = body_node.walk()
            visited_children = False
            while True:
                curr = b_cursor.node
                ntype = curr.type

                if ntype == "call_expression":
                    func_n = curr.child_by_field_name("function")
                    callee = safe_text(func_n)
                    if callee and callee not in CONTROL_KEYWORDS:
                        arg_list = curr.child_by_field_name("arguments")
                        args = []
                        if arg_list:
                            for a in arg_list.named_children:
                                args.append(safe_text(a))
                        call = CCall(callee_name=callee, arguments=args, line_number=curr.start_point[0]+1)
                        fn_def.calls.append(call)
                        result.calls.append(call)

                elif ntype == "assignment_expression":
                    lhs = safe_text(curr.child_by_field_name("left"))
                    rhs = safe_text(curr.child_by_field_name("right"))
                    result.assignments.append(CAssignment(lhs=lhs, rhs=rhs, line_number=curr.start_point[0]+1))

                elif ntype == "init_declarator":
                    decl = curr.child_by_field_name("declarator")
                    val = curr.child_by_field_name("value")
                    lhs = safe_text(decl).lstrip('*').strip()
                    rhs = safe_text(val)
                    result.assignments.append(CAssignment(lhs=lhs, rhs=rhs, line_number=curr.start_point[0]+1, is_declaration=True))

                # Cursor step
                if not visited_children and b_cursor.goto_first_child():
                    continue
                if b_cursor.goto_next_sibling():
                    visited_children = False
                    continue
                if not b_cursor.goto_parent():
                    break
                visited_children = True

            result.functions.append(fn_def)
    return result

print("Running cursor parse on 02.c...")
r = parse_with_cursor(root)
print(f"COMPLETE! Functions: {len(r.functions)}, Calls: {len(r.calls)}, Assignments: {len(r.assignments)}")
for f in r.functions:
    print(f"  Function: {f.name}, calls={len(f.calls)}")
