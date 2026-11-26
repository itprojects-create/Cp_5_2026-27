"""
MacroExpander: C/C++ macro extraction and expansion engine for CryptoFlow.
Preserves source line numbers and ignores macros within string literals or comments.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set


class MacroDefinition:
    def __init__(
        self,
        name: str,
        replacement: Optional[str] = None,
        parameters: Optional[List[str]] = None,
        params: Optional[List[str]] = None,
        body: str = "",
        line_number: int = 1,
        is_function_like: Optional[bool] = None,
    ):
        self.name = name
        if parameters is not None:
            self.params = parameters
        elif params is not None:
            self.params = params
        else:
            self.params = None

        if replacement is not None:
            self.body = replacement
        else:
            self.body = body

        self.line_number = line_number
        if is_function_like is not None:
            self.is_function_like = is_function_like
        else:
            self.is_function_like = self.params is not None

    @property
    def replacement(self) -> str:
        return self.body

    @replacement.setter
    def replacement(self, val: str):
        self.body = val

    @property
    def parameters(self) -> Optional[List[str]]:
        return self.params

    @parameters.setter
    def parameters(self, val: Optional[List[str]]):
        self.params = val


class MacroExpander:
    """
    Parses and expands object-like and function-like C/C++ macros with nested
    expansion support, line preservation, and string/comment safety.
    """

    def __init__(self):
        self.macros: Dict[str, MacroDefinition] = {}
        self._define_spans: List[Tuple[int, int]] = []

    def get_macro(self, name: str) -> Optional[MacroDefinition]:
        """Get macro definition by name."""
        return self.macros.get(name)

    def parse_macros(self, code: str) -> Dict[str, MacroDefinition]:
        """
        Parses all #define directives from code.
        Handles line continuations with backslashes.
        """
        macros: Dict[str, MacroDefinition] = {}
        self._define_spans = []

        # Regex for #define lines with optional backslash continuation
        define_regex = re.compile(r'^[ \t]*#[ \t]*define\s+([A-Za-z_][A-Za-z0-9_]*)(?:\(([^)]*)\))?[ \t]*(.*?)(?=\n(?![ \t]*\\)|$)', re.MULTILINE | re.DOTALL)

        lines = code.splitlines(keepends=True)
        i = 0
        total_lines = len(lines)
        curr_offset = 0

        while i < total_lines:
            line = lines[i]
            line_no = i + 1
            line_start = curr_offset
            stripped = line.strip()

            if stripped.startswith("#"):
                full_directive = stripped
                curr_idx = i
                directive_end = curr_offset + len(line)
                while full_directive.endswith("\\") and curr_idx + 1 < total_lines:
                    curr_idx += 1
                    full_directive = full_directive[:-1].rstrip() + " " + lines[curr_idx].strip()
                    directive_end += len(lines[curr_idx])

                match = re.match(
                    r"^#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)(?:\(([^)]*)\))?(?:[ \t]+(.*))?$",
                    full_directive,
                )
                if match:
                    name = match.group(1)
                    raw_params = match.group(2)
                    raw_body = match.group(3) or ""

                    prefix_match = re.search(
                        r"#[ \t]*define[ \t]+" + re.escape(name) + r"\(", full_directive
                    )
                    is_func_like = bool(prefix_match and raw_params is not None)

                    params = None
                    if is_func_like:
                        params = [p.strip() for p in raw_params.split(",") if p.strip()]

                    body = self._strip_comments_from_str(raw_body).strip()

                    macros[name] = MacroDefinition(
                        name=name,
                        params=params,
                        body=body,
                        line_number=line_no,
                        is_function_like=is_func_like,
                    )
                    self._define_spans.append((line_start, directive_end))
                i = curr_idx
                curr_offset = directive_end
            else:
                curr_offset += len(line)
            i += 1

        self.macros.update(macros)
        return macros

    def expand(self, code: str) -> str:
        """
        Expands all macros in the provided C/C++ source code while preserving
        line numbers and leaving strings and comments untouched.
        Replaces #define directive text with spaces/newlines so macro names in definitions
        do not leak into output.
        """
        self.parse_macros(code)

        # Blank out define lines preserving newlines
        clean_code_chars = list(code)
        for span_start, span_end in self._define_spans:
            for idx in range(span_start, min(span_end, len(clean_code_chars))):
                if clean_code_chars[idx] != '\n':
                    clean_code_chars[idx] = ' '
        code_to_expand = "".join(clean_code_chars)

        tokens_and_spans = self._tokenize(code_to_expand)

        result_chunks = []
        last_end = 0

        idx = 0
        while idx < len(tokens_and_spans):
            token_type, token_val, start, end = tokens_and_spans[idx]

            result_chunks.append(code_to_expand[last_end:start])

            if token_type == "IDENTIFIER" and token_val in self.macros:
                macro = self.macros[token_val]
                if macro.is_function_like:
                    paren_lookahead = self._find_function_call(tokens_and_spans, idx, code_to_expand)
                    if paren_lookahead:
                        call_end_pos, args, new_idx = paren_lookahead
                        expanded = self._expand_function_macro(macro, args, active_stack={token_val})
                        result_chunks.append(expanded)
                        last_end = call_end_pos
                        idx = new_idx + 1
                        continue
                    else:
                        result_chunks.append(token_val)
                else:
                    expanded = self._expand_object_macro(macro, active_stack={token_val})
                    result_chunks.append(expanded)
            else:
                result_chunks.append(token_val)

            last_end = end
            idx += 1

        result_chunks.append(code_to_expand[last_end:])
        return "".join(result_chunks)

    def expand_token(self, token: str) -> str:
        """
        Expands a single token / expression if it matches a known macro.
        """
        if token in self.macros:
            macro = self.macros[token]
            if not macro.is_function_like:
                return self._expand_object_macro(macro, active_stack={token})
        return token

    def _expand_object_macro(self, macro: MacroDefinition, active_stack: Set[str], depth: int = 0) -> str:
        if depth > 50:
            return macro.body
        # Check if the body contains other macros
        tokens = self._tokenize(macro.body)
        expanded_chunks = []
        last_end = 0

        for t_type, t_val, start, end in tokens:
            expanded_chunks.append(macro.body[last_end:start])
            if t_type == "IDENTIFIER" and t_val in self.macros and t_val not in active_stack:
                next_macro = self.macros[t_val]
                if not next_macro.is_function_like:
                    nested = self._expand_object_macro(
                        next_macro, active_stack | {t_val}, depth + 1
                    )
                    expanded_chunks.append(nested)
                else:
                    expanded_chunks.append(t_val)
            else:
                expanded_chunks.append(t_val)
            last_end = end

        expanded_chunks.append(macro.body[last_end:])
        return "".join(expanded_chunks)

    def _expand_function_macro(
        self,
        macro: MacroDefinition,
        args: List[str],
        active_stack: Set[str],
        depth: int = 0,
    ) -> str:
        if depth > 50:
            return macro.body

        body = macro.body
        params = macro.params or []

        # Map parameter names to argument strings
        param_map = {}
        for idx, param in enumerate(params):
            param_map[param] = args[idx] if idx < len(args) else ""

        # Replace parameters in body
        tokens = self._tokenize(body)
        expanded_chunks = []
        last_end = 0

        for t_type, t_val, start, end in tokens:
            expanded_chunks.append(body[last_end:start])
            if t_type == "IDENTIFIER" and t_val in param_map:
                expanded_chunks.append(param_map[t_val])
            else:
                expanded_chunks.append(t_val)
            last_end = end
        expanded_chunks.append(body[last_end:])
        substituted_body = "".join(expanded_chunks)

        # Recursively expand any nested macros in the substituted body
        tokens = self._tokenize(substituted_body)
        final_chunks = []
        last_end = 0
        for t_type, t_val, start, end in tokens:
            final_chunks.append(substituted_body[last_end:start])
            if t_type == "IDENTIFIER" and t_val in self.macros and t_val not in active_stack:
                sub_macro = self.macros[t_val]
                if not sub_macro.is_function_like:
                    nested = self._expand_object_macro(sub_macro, active_stack | {t_val}, depth + 1)
                    final_chunks.append(nested)
                else:
                    final_chunks.append(t_val)
            else:
                final_chunks.append(t_val)
            last_end = end
        final_chunks.append(substituted_body[last_end:])

        return "".join(final_chunks)

    def _find_function_call(
        self, tokens: List[Tuple[str, str, int, int]], start_idx: int, code: str
    ) -> Optional[Tuple[int, List[str], int]]:
        """
        Given the position of a macro identifier, checks if it is immediately followed
        by '(' and finds the matching ')' and parsed comma-separated argument strings.
        """
        # Next token should be '('
        if start_idx + 1 >= len(tokens):
            return None

        next_token = tokens[start_idx + 1]
        # Allow whitespace between identifier and '(', but make sure no other tokens
        if next_token[1] != "(":
            return None

        paren_depth = 0
        args: List[str] = []
        curr_arg_start = next_token[3]  # Just after '('
        call_end_pos = -1
        final_idx = start_idx + 1

        for i in range(start_idx + 1, len(tokens)):
            t_type, t_val, t_start, t_end = tokens[i]
            if t_val == "(":
                paren_depth += 1
            elif t_val == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    arg_str = code[curr_arg_start:t_start].strip()
                    if arg_str or len(args) > 0:
                        args.append(arg_str)
                    call_end_pos = t_end
                    final_idx = i
                    break
            elif t_val == "," and paren_depth == 1:
                arg_str = code[curr_arg_start:t_start].strip()
                args.append(arg_str)
                curr_arg_start = t_end

        if call_end_pos != -1:
            return call_end_pos, args, final_idx
        return None

    def _strip_comments_from_str(self, text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*", "", text)
        return text

    def _tokenize(self, code: str) -> List[Tuple[str, str, int, int]]:
        """
        Splits code into tokens: STRING, CHAR, COMMENT, IDENTIFIER, SYMBOL.
        Returns list of (type, value, start_pos, end_pos).
        """
        pattern = re.compile(
            r"""
            (?P<LINE_COMMENT>//[^\n]*)
            | (?P<BLOCK_COMMENT>/\*.*?\*/)
            | (?P<STRING>L?"(?:\\.|[^"\\])*")
            | (?P<CHAR>L?'(?:\\.|[^'\\])*')
            | (?P<IDENTIFIER>[A-Za-z_][A-Za-z0-9_]*)
            | (?P<SYMBOL>[(),])
            """,
            re.VERBOSE | re.DOTALL,
        )

        tokens = []
        for match in pattern.finditer(code):
            kind = match.lastgroup
            val = match.group(0)
            tokens.append((kind, val, match.start(), match.end()))
        return tokens
