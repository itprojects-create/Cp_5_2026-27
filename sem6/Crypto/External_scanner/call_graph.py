"""
CallGraph: Inter-procedural CallGraphBuilder for C/C++ source trees.
Extracts function definitions, call sites, resolves cross-file references,
and handles function pointer indirect calls up to bounded depth.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from External_scanner.c_parser import CParser


@dataclass
class CallSite:
    caller_name: str
    callee_name: str
    line_number: int
    file_path: str
    is_indirect: bool = False
    pointer_var: Optional[str] = None


@dataclass
class FunctionDef:
    name: str
    file_path: str
    line_number: int
    parameters: List[str] = field(default_factory=list)
    body: str = ""
    is_static: bool = False


@dataclass
class ResolvedCall:
    call_site: CallSite
    target_def: Optional[FunctionDef]
    resolution_path: List[str] = field(default_factory=list)


class CallGraphBuilder:
    """
    Extracts and resolves direct and indirect function calls across multiple C/C++ files.
    """

    def __init__(self, max_indirect_depth: int = 3):
        self.max_indirect_depth = max_indirect_depth
        self.functions: Dict[str, FunctionDef] = {}
        self.call_sites: List[CallSite] = []
        self.function_pointer_assignments: Dict[str, str] = {}  # ptr_name -> func_name
        self.c_parser = CParser()

    def extract_functions(self, file_paths: List[str]) -> List[FunctionDef]:
        """
        Reads and extracts function definitions from multiple C/C++ files.
        """
        definitions: List[FunctionDef] = []
        for path in file_paths:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            defs = self.extract_functions_from_code(code, file_path=path)
            definitions.extend(defs)
            for d in defs:
                self.functions[d.name] = d

        return definitions

    def extract_functions_from_code(self, code: str, file_path: str = "") -> List[FunctionDef]:
        results: List[FunctionDef] = []
        result = self.c_parser.parse(code)

        for fd in result.functions:
            if fd.name in {"if", "for", "while", "switch", "catch"}:
                continue

            fdef = FunctionDef(
                name=fd.name,
                file_path=file_path,
                line_number=fd.line_number,
                parameters=list(fd.parameters),
                body=fd.body,
                is_static=fd.is_static,
            )
            results.append(fdef)
            self.functions[fd.name] = fdef

            # Also detect function pointer assignments within body e.g. fp = &target_func; or fp = target_func;
            self._find_func_ptr_assignments(fd.body)

        return results

    def extract_calls(self, functions: Optional[List[FunctionDef]] = None) -> List[CallSite]:
        """
        Extracts call sites (both direct and through function pointers) from function bodies.
        """
        if functions is None:
            functions = list(self.functions.values())

        call_sites: List[CallSite] = []
        skip = {"if", "for", "while", "switch", "sizeof", "return", "goto", "catch"}

        for fn in functions:
            if not fn.body:
                continue
            # tree-sitter-c rejects bare statements at translation-unit level,
            # so wrap the body in an anonymous function to keep line offsets.
            wrapped = "void _cgraph_anon(void) {\n" + fn.body + "\n}\n"
            body_result = self.c_parser.parse(wrapped)
            for c in body_result.calls:
                callee = c.callee_name
                if callee in skip:
                    continue

                # Check if this callee is a function pointer variable
                is_indirect = callee in self.function_pointer_assignments
                ptr_var = callee if is_indirect else None

                cs = CallSite(
                    caller_name=fn.name,
                    callee_name=callee,
                    line_number=fn.line_number + c.line_number - 1,
                    file_path=fn.file_path,
                    is_indirect=is_indirect,
                    pointer_var=ptr_var,
                )
                call_sites.append(cs)

        self.call_sites.extend(call_sites)
        return call_sites

    def resolve_calls(
        self,
        calls: Optional[List[CallSite]] = None,
        functions: Optional[List[FunctionDef]] = None,
    ) -> List[ResolvedCall]:
        """
        Resolves each call site to its FunctionDef target, resolving indirect calls if needed.
        """
        if calls is None:
            calls = self.call_sites
        if functions is not None:
            for f in functions:
                self.functions[f.name] = f

        resolved: List[ResolvedCall] = []
        for call in calls:
            if call.is_indirect:
                indirect_resolutions = self.handle_indirect_calls(call, depth=self.max_indirect_depth)
                resolved.extend(indirect_resolutions)
            else:
                target_def = self.functions.get(call.callee_name)
                resolved.append(
                    ResolvedCall(
                        call_site=call,
                        target_def=target_def,
                        resolution_path=[call.callee_name],
                    )
                )
        return resolved

    def handle_indirect_calls(self, call: CallSite, depth: int = 3) -> List[ResolvedCall]:
        """
        Resolves function pointer calls through alias chains (fp -> target) up to bounded depth.
        """
        resolutions: List[ResolvedCall] = []
        curr_var = call.pointer_var or call.callee_name
        path = [curr_var]

        for _ in range(min(depth, self.max_indirect_depth)):
            if curr_var in self.function_pointer_assignments:
                target = self.function_pointer_assignments[curr_var]
                path.append(target)
                if target in self.functions:
                    resolutions.append(
                        ResolvedCall(
                            call_site=call,
                            target_def=self.functions[target],
                            resolution_path=path,
                        )
                    )
                    break
                curr_var = target
            else:
                break

        return resolutions

    def get_adjacency_list(self) -> Dict[str, Set[str]]:
        """
        Returns directed call graph as {caller: {callee1, callee2, ...}}.
        """
        adj: Dict[str, Set[str]] = {fn_name: set() for fn_name in self.functions}
        resolved = self.resolve_calls()
        for r in resolved:
            if r.call_site.caller_name in adj:
                target_name = r.target_def.name if r.target_def else r.call_site.callee_name
                adj[r.call_site.caller_name].add(target_name)
        return adj

    def _find_func_ptr_assignments(self, body: str):
        # Matches: fp = &func; or void (*fp)() = &func; or fp = func;
        pattern = re.compile(
            r"(?:\(\s*\*+\s*(?P<decl_ptr>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\([^)]*\)|(?P<ptr>[A-Za-z_][A-Za-z0-9_]*))\s*=\s*(?:&)?(?P<func>[A-Za-z_][A-Za-z0-9_]*)\s*;"
        )
        for match in pattern.finditer(body):
            ptr = match.group("decl_ptr") or match.group("ptr")
            func = match.group("func")
            if ptr and func and ptr != func:
                self.function_pointer_assignments[ptr] = func

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

    def _strip_comments(self, text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*", "", text)
        return text
