"""
rust_parser.py: Tree-sitter powered parser for Rust source code (.rs).
Extracts functions, call sites, static/const declarations, and cryptographic crate API invocations.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    import tree_sitter_rust as tsrust
    from tree_sitter import Language, Parser

    RUST_LANG = Language(tsrust.language())
    _TREE_SITTER_AVAILABLE = True
except Exception:
    RUST_LANG = None
    _TREE_SITTER_AVAILABLE = False


@dataclass
class RustConstDef:
    name: str
    var_type: str
    value: str
    line_number: int
    is_static: bool = False


@dataclass
class RustFunctionDef:
    name: str
    parameters: List[str]
    body: str
    line_number: int
    return_type: Optional[str] = None


@dataclass
class RustCallSite:
    callee_path: str  # e.g., "ring::aead::UnboundKey::new"
    arguments: List[str]
    line_number: int
    assigned_to: Optional[str] = None


@dataclass
class RustPattern:
    """A `let` binding extracted from the source."""

    name: str
    value: str
    line_number: int


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


class RustParser:
    """
    Parses Rust source files, extracting AST items, constants, functions, and crypto API calls.
    """

    def __init__(self):
        self.use_tree_sitter = _TREE_SITTER_AVAILABLE
        if self.use_tree_sitter:
            try:
                self.parser = Parser(RUST_LANG)
            except TypeError:
                self.parser = Parser()
                self.parser.set_language(RUST_LANG)

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        return self.parse_code(code, file_path=file_path)

    def parse_code(self, code: str, file_path: str = "") -> Dict[str, Any]:
        constants = self.extract_constants(code)
        functions = self.extract_functions(code)
        calls = self.extract_calls(code)
        crypto_calls = self.extract_crypto_calls(code)
        let_bindings = self.extract_let_bindings(code)

        return {
            "file_path": file_path,
            "constants": constants,
            "functions": functions,
            "calls": calls,
            "crypto_calls": crypto_calls,
            "let_bindings": let_bindings,
        }

    # ------------------------------------------------------------------ #
    # Tree-sitter helpers
    # ------------------------------------------------------------------ #
    def _parse_tree(self, code: str):
        if not self.use_tree_sitter:
            return None
        return self.parser.parse(code.encode("utf-8"))

    def _field_text(self, node, field_name: str) -> str:
        if node is None:
            return ""
        return _node_text(node.child_by_field_name(field_name) if node else None)

    # ------------------------------------------------------------------ #
    # Constants
    # ------------------------------------------------------------------ #
    def extract_constants(self, code: str) -> List[RustConstDef]:
        constants: List[RustConstDef] = []
        tree = self._parse_tree(code)

        if tree is not None:
            queue = [tree.root_node]
            while queue:
                node = queue.pop(0)
                queue.extend(node.named_children)
                if node.type not in ("const_item", "static_item"):
                    continue
                constants.append(
                    RustConstDef(
                        name=_node_text(node.child_by_field_name("name")),
                        var_type=_node_text(node.child_by_field_name("type")),
                        value=_node_text(node.child_by_field_name("value")),
                        line_number=_node_line(node),
                        is_static=(node.type == "static_item"),
                    )
                )
            return constants

        return self._extract_constants_regex(code)

    def _extract_constants_regex(self, code: str) -> List[RustConstDef]:
        constants = []
        pattern = re.compile(
            r"""
            (?P<kind>const|static)\s+
            (?:mut\s+)?
            (?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*
            (?P<type>[^=]+?)\s*=\s*
            (?P<val>[^;]+?)\s*;
            """,
            re.VERBOSE | re.DOTALL,
        )
        try:
            import os
            lines = code.splitlines()
        except Exception:
            lines = code.splitlines()

        for match in pattern.finditer(code):
            line_no = code[: match.start()].count("\n") + 1
            constants.append(
                RustConstDef(
                    name=match.group("name").strip(),
                    var_type=match.group("type").strip(),
                    value=match.group("val").strip().rstrip(","),
                    line_number=line_no,
                    is_static=(match.group("kind") == "static"),
                )
            )
        return constants

    # ------------------------------------------------------------------ #
    # Functions
    # ------------------------------------------------------------------ #
    def extract_functions(self, code: str) -> List[RustFunctionDef]:
        functions: List[RustFunctionDef] = []
        tree = self._parse_tree(code)

        if tree is not None:
            root = tree.root_node
            for node in root.named_children:
                if node.type != "function_item":
                    continue
                name = _node_text(node.child_by_field_name("name"))
                params_node = node.child_by_field_name("parameters")
                params = []
                if params_node is not None:
                    for param in params_node.named_children:
                        pattern = param.child_by_field_name("pattern")
                        pname = _node_text(pattern)
                        if not pname:
                            continue
                        pname = self._strip_prefix(pname, "&mut ")
                        pname = self._strip_prefix(pname, "mut ")
                        pname = self._strip_prefix(pname, "&")
                        pname = self._strip_prefix(pname, "*")
                        params.append(pname)
                functions.append(
                    RustFunctionDef(
                        name=name,
                        parameters=params,
                        body=_node_text(node.child_by_field_name("body")),
                        line_number=_node_line(node),
                        return_type=_node_text(node.child_by_field_name("return_type")) or None,
                    )
                )
            return functions

        return self._extract_functions_regex(code)

    def _extract_functions_regex(self, code: str) -> List[RustFunctionDef]:
        functions = []
        fn_pattern = re.compile(
            r"""
            (?:pub\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+
            (?P<name>[A-Za-z_][A-Za-z0-9_]*)
            \s*\((?P<params>[^)]*)\)
            (?:\s*->\s*(?P<ret>[^{]+))?
            \s*\{
            """,
            re.VERBOSE,
        )

        for match in fn_pattern.finditer(code):
            name = match.group("name")
            raw_params = match.group("params") or ""
            ret_type = match.group("ret").strip() if match.group("ret") else None
            start_pos = match.end() - 1
            body, _ = self._extract_block(code, start_pos)
            line_no = code[: match.start()].count("\n") + 1

            params = []
            for p in raw_params.split(","):
                p_clean = p.strip()
                if not p_clean:
                    continue
                pname = p_clean.split(":")[0].strip()
                pname = self._strip_prefix(pname, "&mut ")
                pname = self._strip_prefix(pname, "mut ")
                pname = self._strip_prefix(pname, "&")
                if pname:
                    params.append(pname)

            functions.append(
                RustFunctionDef(
                    name=name,
                    parameters=params,
                    body=body,
                    line_number=line_no,
                    return_type=ret_type,
                )
            )
        return functions

    # ------------------------------------------------------------------ #
    # Calls
    # ------------------------------------------------------------------ #
    def extract_calls(self, code: str) -> List[RustCallSite]:
        calls: List[RustCallSite] = []
        tree = self._parse_tree(code)

        if tree is not None:
            self._collect_calls(tree.root_node, calls)
            return calls

        return self._extract_calls_regex(code)

    def _collect_calls(self, node, calls: List[RustCallSite]) -> None:
        if node is None:
            return
        if node.type == "call_expression":
            call = self._make_call(node)
            if call is not None:
                calls.append(call)
            # Chained calls (e.g. `foo()(..)` or `foo().method(..)`): the base
            # call lives in the *function* field; still capture it, but do not
            # descend into the argument list (avoids duplicating nested args).
            func_node = node.child_by_field_name("function")
            if func_node is not None and func_node.type != "identifier" and func_node.type != "scoped_identifier":
                for child in func_node.named_children:
                    self._collect_calls(child, calls)
            return
        for child in node.named_children:
            self._collect_calls(child, calls)

    def _make_call(self, node) -> Optional[RustCallSite]:
        func_node = node.child_by_field_name("function")
        if func_node is None:
            return None

        if func_node.type == "scoped_identifier" or func_node.type == "identifier":
            callee = _node_text(func_node)
        elif func_node.type == "field_expression":
            named = func_node.named_children
            tail = _node_text(named[-1]) if named else ""
            has_base_call = self._contains_type(func_node, "call_expression")
            if has_base_call:
                # `base_call.method(..)`: name the outer call by the method tail;
                # the base call itself is captured separately.
                callee = tail or _node_text(func_node)
            else:
                callee = _node_text(func_node)
        else:
            callee = _node_text(func_node)

        if not callee:
            return None

        args = []
        arg_list = node.child_by_field_name("arguments")
        if arg_list is not None:
            args = [_node_text(a) for a in arg_list.named_children]

        assigned = None
        parent = getattr(node, "parent", None)
        if parent is not None and parent.type == "let_declaration":
            assigned = _node_text(parent.child_by_field_name("pattern"))

        return RustCallSite(
            callee_path=callee,
            arguments=args,
            line_number=_node_line(node),
            assigned_to=assigned,
        )

    @staticmethod
    def _contains_type(node, type_name: str) -> bool:
        if node is None:
            return False
        if node.type == type_name:
            return True
        return any(RustParser._contains_type(c, type_name) for c in node.named_children)

    def _extract_calls_regex(self, code: str) -> List[RustCallSite]:
        calls = []
        call_pattern = re.compile(
            r"""
            (?:let\s+(?:mut\s+)?(?P<assign>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?
            (?P<callee>(?:[A-Za-z_][A-Za-z0-9_]*::)+[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)
            \s*\((?P<args>[^)]*)\)
            """,
            re.VERBOSE,
        )

        for match in call_pattern.finditer(code):
            callee = match.group("callee")
            if callee in {"if", "match", "while", "for", "println", "eprintln", "vec", "panic"}:
                continue

            raw_args = match.group("args") or ""
            args = [a.strip() for a in raw_args.split(",") if a.strip()]
            line_no = code[: match.start()].count("\n") + 1
            assigned = match.group("assign")

            calls.append(
                RustCallSite(
                    callee_path=callee,
                    arguments=args,
                    line_number=line_no,
                    assigned_to=assigned,
                )
            )
        return calls

    # ------------------------------------------------------------------ #
    # Let bindings
    # ------------------------------------------------------------------ #
    def extract_let_bindings(self, code: str) -> List[RustPattern]:
        bindings: List[RustPattern] = []
        tree = self._parse_tree(code)

        if tree is not None:
            queue = [tree.root_node]
            while queue:
                node = queue.pop(0)
                queue.extend(node.named_children)
                if node.type != "let_declaration":
                    continue
                name = _node_text(node.child_by_field_name("pattern"))
                value = _node_text(node.child_by_field_name("value"))
                if name and value:
                    bindings.append(RustPattern(name=name, value=value, line_number=_node_line(node)))
            return bindings

        for idx, line in enumerate(code.splitlines(), start=1):
            m = re.search(r"let\s+(?:mut\s+)?(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[^;]+);", line)
            if m:
                bindings.append(
                    RustPattern(
                        name=m.group("var").strip(),
                        value=m.group("val").strip(),
                        line_number=idx,
                    )
                )
        return bindings

    def extract_crypto_calls(self, code: str) -> List[RustCallSite]:
        """
        Filters calls for known Rust crypto crate namespaces (ring, rustls, openssl, getrandom).
        """
        all_calls = self.extract_calls(code)
        crypto_namespaces = ("ring::", "rustls::", "openssl::", "getrandom::")
        return [c for c in all_calls if any(c.callee_path.startswith(ns) for ns in crypto_namespaces)]

    # ------------------------------------------------------------------ #
    # Misc
    # ------------------------------------------------------------------ #
    @staticmethod
    def _strip_prefix(text: str, prefix: str) -> str:
        if text.startswith(prefix):
            return text[len(prefix):]
        return text

    def _extract_block(self, text: str, open_brace_idx: int) -> Tuple[str, int]:
        depth = 0
        for i in range(open_brace_idx, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[open_brace_idx + 1 : i], i
        return text[open_brace_idx + 1 :], len(text)