import sys, re
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from External_scanner.c_parser import _node_text

fp = Path('datasets/juliet/testcases/CWE321_Hard_Coded_Cryptographic_Key/CWE321_Hard_Coded_Cryptographic_Key__w32_char_02.c')
code = fp.read_text(encoding='utf-8', errors='ignore')
code = re.sub(r'#ifndef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#ifdef\s+OMIT\w+\r?\n', '', code)
code = re.sub(r'#endif(?:\s+/\*[^*]*\*/)?\r?\n', '\n', code)

import tree_sitter_c as tsc
from tree_sitter import Language, Parser

tree = Parser(Language(tsc.language())).parse(code.encode('utf-8'))
root = tree.root_node

fn8 = root.children[8]
fn12 = root.children[12]

def find_crypt_encrypt(n):
    if n.type == "call_expression" and "CryptEncrypt" in _node_text(n):
        return n
    for c in n.children:
        r = find_crypt_encrypt(c)
        if r: return r
    return None

c8 = find_crypt_encrypt(fn8)
c12 = find_crypt_encrypt(fn12)

print("CryptEncrypt in fn8:")
print(_node_text(c8))
print("CryptEncrypt in fn12:")
print(_node_text(c12))
print("Are they byte-equal?:", c8.text == c12.text)
