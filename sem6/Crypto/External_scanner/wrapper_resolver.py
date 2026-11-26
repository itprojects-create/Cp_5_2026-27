"""
WrapperResolver: Detects crypto API wrapper functions and constructs transitive wrapper call chains.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Union

from External_scanner.c_parser import CParser, CCall, CFuncDef


DEFAULT_CRYPTO_APIS = {
    "EVP_EncryptInit_ex",
    "EVP_DecryptInit_ex",
    "EVP_CipherInit_ex",
    "AES_set_encrypt_key",
    "AES_set_decrypt_key",
    "RSA_public_encrypt",
    "RSA_private_decrypt",
    "CryptHashData",
    "CryptDeriveKey",
    "CryptEncrypt",
    "CryptDecrypt",
    "MD5_Init",
    "SHA256_Init",
    "DES_set_key",
}


@dataclass
class Call:
    callee_name: str
    arguments: List[str]
    line_number: int = 1
    return_assigned_to: Optional[str] = None


@dataclass
class Function:
    name: str
    return_type: str = "void"
    parameters: List[str] = field(default_factory=list)
    body: str = ""
    file_path: str = ""
    line_number: int = 1
    calls: List[Call] = field(default_factory=list)
    returns_value: bool = False


@dataclass
class WrapperFunction:
    name: str = ""
    target_crypto_api: str = ""
    chain: List[str] = field(default_factory=list)  # e.g., ["wrapperA", "wrapperB", "EVP_EncryptInit_ex"]
    depth: int = 1
    parameters: List[str] = field(default_factory=list)
    param_to_crypto_arg: Dict[int, int] = field(default_factory=dict)
    returns_crypto_val: bool = False
    definition: Optional[Function] = None
    return_type: str = "void"
    body: str = ""
    file_path: str = ""
    line_number: int = 1
    _crypto_calls: List[str] = field(default_factory=list)

    @property
    def crypto_calls(self) -> List[str]:
        if self._crypto_calls:
            return self._crypto_calls
        return [self.target_crypto_api] if self.target_crypto_api else []

    @crypto_calls.setter
    def crypto_calls(self, val: List[str]):
        self._crypto_calls = list(val)
        if val and not self.target_crypto_api:
            self.target_crypto_api = val[0]


@dataclass
class ArgumentMapping:
    caller_args: List[str]
    wrapper_params: List[str]
    crypto_api_args: List[str]
    target_api: str


@dataclass
class CallMapping:
    caller: str
    callee: str
    argument_to_param: Dict[int, int] = field(default_factory=dict)


class CallGraph(dict):
    def __init__(self):
        super().__init__()
        self.functions: Dict[str, Function] = {}
        self.edges: List[Tuple[str, str, Call]] = []
        self.wrappers: Dict[str, WrapperFunction] = {}

    def __getitem__(self, item: str) -> List[str]:
        if item in self:
            return super().__getitem__(item)
        return [callee for caller, callee, _ in self.edges if caller == item]

    def get(self, item: str, default=None):
        res = [callee for caller, callee, _ in self.edges if caller == item]
        return res if res else (default if default is not None else [])


class WrapperResolver:
    """
    Identifies wrapper functions over cryptographic APIs and tracks call graphs
    and argument-parameter mappings up to depth 5.
    """

    CRYPTO_APIS = set(DEFAULT_CRYPTO_APIS) | {
        "EVP_EncryptInit_ex", "EVP_DecryptInit_ex", "EVP_EncryptUpdate",
        "AES_set_encrypt_key", "AES_encrypt", "AES_decrypt",
        "SHA256_Init", "SHA256_Update", "SHA256_Final",
        "CryptEncrypt", "CryptDecrypt", "CryptGenKey",
    }

    def __init__(self, crypto_apis: Optional[Set[str]] = None, max_depth: int = 5):
        self.crypto_apis = set(crypto_apis) if crypto_apis else set(self.CRYPTO_APIS)
        self.max_depth = max_depth
        self.functions: Dict[str, Function] = {}
        self.wrappers: Dict[str, WrapperFunction] = {}
        self.call_graph: Dict[str, List[str]] = {}
        self.c_parser = CParser()

    def extract_functions(self, code: str, file_path: str = "source.c") -> List[Function]:
        funcs = self.parse_functions(code)
        for f in funcs:
            f.file_path = file_path
            self.functions[f.name] = f
        return funcs

    def parse_functions(self, code: str) -> List[Function]:
        """
        Parses C/C++ function definitions, parameters, and calls using the
        tree-sitter backed CParser (regex fallback if the grammar is missing).
        """
        functions: List[Function] = []
        result = self.c_parser.parse(code)

        for fd in result.functions:
            calls = [
                Call(
                    callee_name=c.callee_name,
                    arguments=c.arguments,
                    line_number=c.line_number,
                    return_assigned_to=c.return_assigned_to,
                )
                for c in fd.calls
            ]
            returns_value = bool(re.search(r"\breturn\s+[^;]+;", fd.body))

            functions.append(
                Function(
                    name=fd.name,
                    return_type=fd.return_type,
                    parameters=list(fd.parameters),
                    body=fd.body,
                    line_number=fd.line_number,
                    calls=calls,
                    returns_value=returns_value,
                )
            )

        return functions

    def find_wrappers(self, code_or_functions: Any) -> List[WrapperFunction]:
        """
        Finds all functions in code (or Function objects) that transitively call cryptographic APIs up to max_depth.
        """
        if isinstance(code_or_functions, str):
            functions = self.extract_functions(code_or_functions)
        else:
            functions = list(code_or_functions)
            for f in functions:
                self.functions[f.name] = f
        call_graph = self.build_call_graph(functions)
        self.wrappers = call_graph.wrappers
        return list(call_graph.wrappers.values())

    def build_call_graph(self, functions: List[Function]) -> CallGraph:
        """
        Builds a CallGraph from a list of Function objects and identifies wrapper functions.
        """
        graph = CallGraph()
        call_map: Dict[str, List[str]] = {}
        for fn in functions:
            graph.functions[fn.name] = fn
            self.functions[fn.name] = fn
            call_map[fn.name] = []

        for fn in functions:
            for call in fn.calls:
                graph.edges.append((fn.name, call.callee_name, call))
                if call.callee_name not in call_map[fn.name]:
                    call_map[fn.name].append(call.callee_name)

        for caller, callees in call_map.items():
            graph[caller] = callees
        self.call_graph = call_map

        # Direct crypto wrappers (depth 1)
        wrappers: Dict[str, WrapperFunction] = {}

        for fn in functions:
            crypto_calls_found = []
            for api in self.crypto_apis:
                if any(call.callee_name == api for call in fn.calls):
                    crypto_calls_found.append(api)

            if crypto_calls_found:
                primary_api = crypto_calls_found[0]
                param_map = {}
                # Match parameters if calls exist
                for call in fn.calls:
                    if call.callee_name == primary_api:
                        for c_idx, arg in enumerate(call.arguments):
                            arg_clean = arg.strip()
                            if arg_clean in fn.parameters:
                                p_idx = fn.parameters.index(arg_clean)
                                param_map[p_idx] = c_idx

                wrapper = WrapperFunction(
                    name=fn.name,
                    target_crypto_api=primary_api,
                    chain=[fn.name, primary_api],
                    depth=1,
                    parameters=fn.parameters,
                    param_to_crypto_arg=param_map,
                    returns_crypto_val=fn.returns_value,
                    definition=fn,
                    return_type=fn.return_type,
                    body=fn.body,
                    file_path=fn.file_path,
                    line_number=fn.line_number,
                    _crypto_calls=crypto_calls_found,
                )
                wrappers[fn.name] = wrapper

        # Transitive wrappers up to max_depth
        for current_depth in range(2, self.max_depth + 1):
            added_any = False
            for fn in functions:
                if fn.name in wrappers:
                    continue
                # Check calls or regex
                callees = call_map.get(fn.name, [])
                for callee_name in callees:
                    if callee_name in wrappers and wrappers[callee_name].depth < current_depth:
                        sub_wrapper = wrappers[callee_name]
                        param_map = {}
                        for call in fn.calls:
                            if call.callee_name == callee_name:
                                for c_idx, arg in enumerate(call.arguments):
                                    arg_clean = arg.strip()
                                    if arg_clean in fn.parameters:
                                        p_idx = fn.parameters.index(arg_clean)
                                        if c_idx in sub_wrapper.param_to_crypto_arg:
                                            param_map[p_idx] = sub_wrapper.param_to_crypto_arg[c_idx]

                        wrappers[fn.name] = WrapperFunction(
                            name=fn.name,
                            target_crypto_api=sub_wrapper.target_crypto_api,
                            chain=[fn.name] + sub_wrapper.chain,
                            depth=sub_wrapper.depth + 1,
                            parameters=fn.parameters,
                            param_to_crypto_arg=param_map,
                            returns_crypto_val=fn.returns_value,
                            definition=fn,
                            return_type=fn.return_type,
                            body=fn.body,
                            file_path=fn.file_path,
                            line_number=fn.line_number,
                            _crypto_calls=sub_wrapper.crypto_calls,
                        )
                        added_any = True
                        break
            if not added_any:
                break

        graph.wrappers = wrappers
        self.wrappers = wrappers
        return graph

    def resolve_transitive_wrappers(self, caller: str, depth: int = 0) -> List[str]:
        """
        Find transitive wrapper chain from caller to crypto API.
        """
        if depth > self.max_depth:
            return []

        if caller in self.wrappers:
            w = self.wrappers[caller]
            if getattr(w, "depth", 1) > 1 and getattr(w, "chain", None) and len(w.chain) > 1:
                return w.chain[1:]
            return w.crypto_calls

        chain = []
        callees = self.call_graph.get(caller, [])
        for callee in callees:
            sub_chain = self.resolve_transitive_wrappers(callee, depth + 1)
            if sub_chain:
                chain.extend([callee] + [c for c in sub_chain if c != callee])
                break

        return chain

    def map_arguments(self, caller_or_call: Any, callee_or_wrapper: Any = None) -> Any:
        """
        Maps arguments from caller to callee parameters or wrapper crypto arguments.
        """
        if isinstance(caller_or_call, str):
            caller_name = caller_or_call
            callee_name = str(callee_or_wrapper)
            caller_func = self.functions.get(caller_name)
            callee_func = self.functions.get(callee_name)

            arg_to_param = {}
            if caller_func and callee_func:
                pattern = rf'\b{callee_name}\s*\(([^)]*)\)'
                match = re.search(pattern, caller_func.body)
                if match:
                    call_args_str = match.group(1)
                    call_args = [a.strip() for a in call_args_str.split(',') if a.strip()]
                    for i in range(min(len(call_args), len(callee_func.parameters))):
                        arg_to_param[i] = i

            return CallMapping(caller=caller_name, callee=callee_name, argument_to_param=arg_to_param)

        call = caller_or_call
        wrapper = callee_or_wrapper
        crypto_args = [""] * 10
        for p_idx, c_idx in wrapper.param_to_crypto_arg.items():
            if p_idx < len(call.arguments):
                arg_val = call.arguments[p_idx]
                if c_idx < len(crypto_args):
                    crypto_args[c_idx] = arg_val

        while crypto_args and not crypto_args[-1]:
            crypto_args.pop()

        return ArgumentMapping(
            caller_args=call.arguments,
            wrapper_params=wrapper.parameters,
            crypto_api_args=crypto_args,
            target_api=wrapper.target_crypto_api,
        )

    def _extract_calls(self, body: str, base_line: int) -> List[Call]:
        """
        Finds function call expressions inside function body.
        """
        calls = []
        call_pattern = re.compile(
            r"""
            (?:(?P<assign>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)?
            (?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(
            """,
            re.VERBOSE,
        )

        lines = body.splitlines(keepends=True)
        char_offsets = [0]
        for l in lines:
            char_offsets.append(char_offsets[-1] + len(l))

        for match in call_pattern.finditer(body):
            name = match.group("name")
            if name in {"if", "for", "while", "switch", "sizeof", "return"}:
                continue

            assign_var = match.group("assign")
            paren_start = match.end() - 1
            # Find closing paren
            depth = 0
            call_args_str = ""
            for i in range(paren_start, len(body)):
                if body[i] == "(":
                    depth += 1
                elif body[i] == ")":
                    depth -= 1
                    if depth == 0:
                        call_args_str = body[paren_start + 1 : i]
                        break

            # Parse arguments
            args = []
            if call_args_str.strip():
                # Split by commas not inside nested parens
                cur_arg = []
                p_depth = 0
                for ch in call_args_str:
                    if ch == "(":
                        p_depth += 1
                        cur_arg.append(ch)
                    elif ch == ")":
                        p_depth -= 1
                        cur_arg.append(ch)
                    elif ch == "," and p_depth == 0:
                        args.append("".join(cur_arg).strip())
                        cur_arg = []
                    else:
                        cur_arg.append(ch)
                if cur_arg:
                    args.append("".join(cur_arg).strip())

            # Calculate line number
            match_offset = match.start()
            line_idx = 0
            for idx, off in enumerate(char_offsets):
                if off > match_offset:
                    line_idx = max(0, idx - 1)
                    break
            line_no = base_line + line_idx

            calls.append(
                Call(
                    callee_name=name,
                    arguments=args,
                    line_number=line_no,
                    return_assigned_to=assign_var,
                )
            )

        return calls

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
