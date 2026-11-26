import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from External_scanner.c_parser import CParser, CParseResult, _node_text

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

cp = CParser()
source_bytes = code.encode('utf-8')
tree = cp.parser.parse(source_bytes)
root = tree.root_node

for idx, n in enumerate(root.children):
    sys.stdout.write(f"Root child {idx}: {n.type}\n")
    sys.stdout.flush()
    if n.type == "function_definition":
        res = CParseResult()
        sys.stdout.write(f"  Extracting function {idx}...\n")
        sys.stdout.flush()
        cp._extract_function(n, res)
        sys.stdout.write(f"  Extracted: {res.functions[-1].name}, calls={len(res.calls)}\n")
        sys.stdout.flush()

print("All root children extracted successfully!")
