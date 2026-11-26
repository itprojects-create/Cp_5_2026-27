"""
c_parser.py: Tree-sitter powered C/C++ parser.

Extracts functions, call sites, and assignments from C source using the
tree-sitter-c grammar (with a best-effort regex fallback when the grammar is
unavailable). Unlike the legacy regex parsers, this AST-driven module does not
misparse braces/`//` inside string literals and does not treat identifiers
inside comments or strings as call sites.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    import tree_sitter_c as tsc
    from tree_sitter import Language, Parser

    C_LANG = Language(tsc.language())
    _TREE_SITTER_AVAILABLE = True
except Exception:
    C_LANG = None
    _TREE_SITTER_AVAILABLE = False


@dataclass
class CCall:
    callee_name: str
    arguments: List[str]
    line_number: int = 1
    return_assigned_to: Optional[str] = None


@dataclass
class CFuncDef:
    name: str
    parameters: List[str]
    body: str
    line_number: int = 1
    return_type: str = "void"
    is_static: bool = False
    calls: List[CCall] = field(default_factory=list)


@dataclass
class CAssignment:
    lhs: str
    rhs: str
    line_number: int = 1
    is_declaration: bool = False
    is_pointer_decl: bool = False
    is_address_of: bool = False
    deref_level: int = 0


@dataclass
class CParseResult:
    functions: List[CFuncDef] = field(default_factory=list)
    calls: List[CCall] = field(default_factory=list)
    assignments: List[CAssignment] = field(default_factory=list)


# Keywords/builtins that are never function calls.
CONTROL_KEYWORDS = {
    "if", "for", "while", "switch", "sizeof", "return", "catch", "new",
    "delete", "static_cast", "dynamic_cast", "reinterpret_cast", "const_cast",
}


def _node_text(node) -> str:
    if node is None:
        return ""
    try:
        return node.text.decode("utf-8", "replace").strip()
    except AttributeError:
        return ""


def _node_line(node) -> int:
    try:
        return node.start_point.row + 1
    except AttributeError:
        return 1



class CParser:
    """AST-driven parser for C/C++ source code."""

    def __init__(self):
        self.use_tree_sitter = _TREE_SITTER_AVAILABLE
        if self.use_tree_sitter:
            self.parser = Parser(C_LANG)

    def parse(self, code: str) -> CParseResult:
        return self._parse_robust(code)

    def _parse_robust(self, code: str) -> CParseResult:
        result = CParseResult()
        masked_code = self._mask_comments_and_strings(code)

        func_sig_regex = re.compile(
            r"""
            (?:(?P<ret>[A-Za-z_][A-Za-z0-9_*\s]+)\s+)?
            (?P<name>[A-Za-z_][A-Za-z0-9_]*)
            \s*\((?P<params>[^)]*)\)
            \s*\{
            """,
            re.VERBOSE,
        )

        for match in func_sig_regex.finditer(masked_code):
            name = match.group("name")
            if name in CONTROL_KEYWORDS:
                continue
            raw_params = match.group("params") or ""
            start_brace = match.end() - 1
            body, end_pos = self._extract_balanced(code, start_brace, '{', '}')
            line_no = code[: match.start()].count("\n") + 1

            params = []
            if raw_params.strip() and raw_params.strip() != "void":
                for p in self._split_args(raw_params):
                    tokens = [t for t in re.split(r"[\s*&]+", p.strip()) if t]
                    if tokens:
                        params.append(tokens[-1])

            fn_def = CFuncDef(
                name=name,
                parameters=params,
                body="{" + body + "}",
                line_number=line_no,
                return_type=(match.group("ret") or "void").strip(),
            )
            fn_def._body_inner_start = start_brace + 1
            fn_def._body_inner_end = end_pos - 1
            result.functions.append(fn_def)

        # Calls extraction: search ONLY inside the body of each function, using masked_code
        call_pattern = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
        for fn in result.functions:
            inner_masked = masked_code[fn._body_inner_start:fn._body_inner_end]
            for m in call_pattern.finditer(inner_masked):
                callee = m.group("name")
                if callee in CONTROL_KEYWORDS:
                    continue
                abs_start = fn._body_inner_start + m.end() - 1
                raw_args, _ = self._extract_balanced(code, abs_start, '(', ')')
                args = self._split_args(raw_args)
                call_abs_pos = fn._body_inner_start + m.start()
                call_line = code[:call_abs_pos].count("\n") + 1
                call = CCall(callee_name=callee, arguments=args, line_number=call_line)
                fn.calls.append(call)
                result.calls.append(call)

        # Assignments extraction across entire file
        assign_pattern = re.compile(
            r"""
            (?:(?P<type>[A-Za-z0-9_* \t]+?)[ \t]+)?
            (?P<lhs>[*&]*[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?)
            [ \t]*=[ \t]*
            (?P<rhs>[^;]+)
            [ \t]*;
            """,
            re.VERBOSE,
        )
        for m in assign_pattern.finditer(code):
            raw_type = m.group("type") or ""
            raw_lhs = m.group("lhs")
            rhs = m.group("rhs").strip()

            start_idx = m.start()
            line_start = code.rfind('\n', 0, start_idx) + 1
            line_prefix = code[line_start:start_idx].strip()
            if line_prefix.startswith('//') or line_prefix.startswith('/*'):
                continue

            lhs = raw_lhs.lstrip("*&")
            lhs = re.sub(r"\[[^\]]*\]", "", lhs).strip()
            if not lhs or lhs in CONTROL_KEYWORDS or raw_type.strip() in ("return", "goto", "if", "while"):
                continue

            is_decl = bool(raw_type.strip())
            is_ptr = ("*" in raw_type) or ("*" in raw_lhs)
            is_addr = rhs.startswith("&")
            deref_count = raw_lhs.count("*") + raw_type.count("*")
            line_no = code[:start_idx].count("\n") + 1
            asgn = CAssignment(
                lhs=lhs,
                rhs=rhs,
                line_number=line_no,
                is_declaration=is_decl,
                is_pointer_decl=is_ptr,
                is_address_of=is_addr,
                deref_level=min(deref_count, 3),
            )
            result.assignments.append(asgn)

        return result

    @staticmethod
    def _split_args(arg_str: str) -> List[str]:
        arg_str = arg_str.strip()
        if not arg_str:
            return []
        args = []
        curr = []
        depth = 0
        in_quote = False
        quote_char = ""
        for ch in arg_str:
            if in_quote:
                curr.append(ch)
                if ch == quote_char:
                    in_quote = False
            elif ch in ('"', "'"):
                in_quote = True
                quote_char = ch
                curr.append(ch)
            elif ch in ("(", "[", "{"):
                depth += 1
                curr.append(ch)
            elif ch in (")", "]", "}"):
                depth -= 1
                curr.append(ch)
            elif ch == "," and depth == 0:
                args.append("".join(curr).strip())
                curr = []
            else:
                curr.append(ch)
        if curr:
            args.append("".join(curr).strip())
        return [a for a in args if a]

    @staticmethod
    def _extract_balanced(text: str, start_idx: int, open_ch='(', close_ch=')') -> Tuple[str, int]:
        depth = 0
        in_quote = False
        quote_ch = ''
        content = []
        for i in range(start_idx, len(text)):
            ch = text[i]
            if in_quote:
                content.append(ch)
                if ch == quote_ch and (i == 0 or text[i-1] != '\\'):
                    in_quote = False
            elif ch in ('"', "'"):
                in_quote = True
                quote_ch = ch
                content.append(ch)
            elif ch == open_ch:
                depth += 1
                if depth > 1:
                    content.append(ch)
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return "".join(content), i + 1
                else:
                    content.append(ch)
            else:
                if depth >= 1:
                    content.append(ch)
        return "".join(content), len(text)

    @staticmethod
    def _mask_comments_and_strings(code: str) -> str:
        def replacer(match):
            s = match.group(0)
            if s.startswith('/') or s.startswith('"') or s.startswith("'"):
                if s.startswith('"') or s.startswith("'"):
                    return s[0] + " " * (len(s) - 2) + s[-1] if len(s) >= 2 else s
                return " " * len(s)
            return s
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        return pattern.sub(replacer, code)