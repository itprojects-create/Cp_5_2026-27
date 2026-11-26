"""
AliasAnalyzer: Disjoint-set based pointer and alias analysis for C/C++.
Tracks pointer assignments, reference taking (&var), dereferences (*ptr),
and integrates with FlowTracker to reflect shared flows across aliased variables.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from External_scanner.c_parser import CParser


@dataclass
class PointerAssignment:
    lhs: str
    rhs: str
    is_address_of: bool = False
    deref_level: int = 0
    line_number: int = 1


class UnionFind:
    """
    Disjoint-set forest with path compression and union by rank.
    """

    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
            self.rank[item] = 0
            return item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, item1: str, item2: str):
        root1 = self.find(item1)
        root2 = self.find(item2)
        if root1 == root2:
            return

        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1

    def get_groups(self) -> List[Set[str]]:
        groups: Dict[str, Set[str]] = {}
        for item in list(self.parent.keys()):
            root = self.find(item)
            if root not in groups:
                groups[root] = set()
            groups[root].add(item)
        return list(groups.values())


class AliasAnalyzer:
    """
    Analyzes pointer assignments and constructs alias sets.
    """

    def __init__(self, max_deref_depth: int = 3):
        self.max_deref_depth = max_deref_depth
        self.uf = UnionFind()
        self.assignments: List[PointerAssignment] = []
        self.c_parser = CParser()

    @property
    def parent(self) -> Dict[str, str]:
        return self.uf.parent

    @property
    def rank(self) -> Dict[str, int]:
        return self.uf.rank

    def find(self, var: str) -> str:
        return self.uf.find(var)

    def union(self, var1: str, var2: str):
        self.uf.union(var1, var2)

    def add_pointer_assignment(self, ptr: str, target: str):
        self.union(ptr, target)

    def add_pointer_copy(self, ptr1: str, ptr2: str):
        self.union(ptr1, ptr2)

    def parse_pointer_assignments(self, code: str) -> List[tuple]:
        """
        Parse pointer assignments from code: ptr = &target, ptr1 = ptr2.
        """
        assignments = []
        pattern1 = r'(\w+)\s*=\s*&\s*(\w+)'
        for match in re.finditer(pattern1, code):
            ptr = match.group(1)
            target = match.group(2)
            assignments.append((ptr, target))
            self.add_pointer_assignment(ptr, target)

        pattern2 = r'(\w+)\s*=\s*(\w+)'
        for match in re.finditer(pattern2, code):
            ptr1 = match.group(1)
            ptr2 = match.group(2)
            if ptr1 != ptr2 and not ptr2.isdigit():
                assignments.append((ptr1, ptr2))
                self.add_pointer_copy(ptr1, ptr2)

        return assignments

    def find_pointer_assignments(self, code: str) -> List[PointerAssignment]:
        """
        Extracts pointer assignments using the AST parser:
        - ptr = &var
        - ptr1 = ptr2  (pointer-typed lhs)
        - sptr = &struct_var
        - aptr = array_var
        Non-pointer copies (e.g. `int x = y;`) are deliberately NOT aliased.
        """
        assignments: List[PointerAssignment] = []
        result = self.c_parser.parse(code)

        for a in result.assignments:
            if not a.lhs or not a.rhs:
                continue
            rhs = a.rhs.strip()
            if not a.is_address_of and not a.is_pointer_decl and not rhs.startswith("*"):
                continue
            if rhs.startswith('"') or rhs.startswith('L"') or rhs.isdigit():
                continue

            clean_lhs = a.lhs.strip().lstrip("*")
            clean_rhs = rhs.lstrip("&*").strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", clean_rhs):
                continue
            if clean_lhs == clean_rhs:
                continue

            pa = PointerAssignment(
                lhs=clean_lhs,
                rhs=clean_rhs,
                is_address_of=a.is_address_of,
                deref_level=min(a.deref_level, self.max_deref_depth),
                line_number=a.line_number,
            )
            assignments.append(pa)
            self.union(clean_lhs, clean_rhs)

        self.assignments.extend(assignments)
        return assignments

    def build_alias_sets(self, assignments: Optional[List[PointerAssignment]] = None) -> List[Set[str]]:
        """
        Builds alias sets from pointer assignments using the UnionFind data structure.
        """
        if assignments is None:
            assignments = self.assignments

        for pa in assignments:
            self.uf.union(pa.lhs, pa.rhs)

        return self.uf.get_groups()

    def may_alias(self, var1: str, var2: str) -> bool:
        """
        Returns True if var1 and var2 belong to the same alias set.
        """
        if var1 not in self.uf.parent or var2 not in self.uf.parent:
            return False
        return self.uf.find(var1) == self.uf.find(var2)

    def get_aliases(self, variable: str) -> Set[str]:
        """
        Returns all variables known to alias with the given variable.
        """
        if variable not in self.uf.parent:
            return set()
        root = self.uf.find(variable)
        aliases = set()
        for item in list(self.uf.parent.keys()):
            if self.uf.find(item) == root:
                aliases.add(item)
        return aliases

    def integrate_with_flow_tracker(self, flow_tracker):
        """
        Connects aliased variables in the FlowTracker global graph with ALIASES edges.
        """
        alias_groups = self.build_alias_sets()
        for group in alias_groups:
            group_list = list(group)
            for i in range(len(group_list)):
                for j in range(i + 1, len(group_list)):
                    var1, var2 = group_list[i], group_list[j]
                    # Find all nodes in flow tracker matching var1 and var2
                    v1_nodes = [n for n in flow_tracker.global_graph.nodes.values() if n.name == var1]
                    v2_nodes = [n for n in flow_tracker.global_graph.nodes.values() if n.name == var2]
                    for n1 in v1_nodes:
                        for n2 in v2_nodes:
                            flow_tracker.global_graph.add_edge(n1.id, n2.id, "ALIASES", 0.9)
                            flow_tracker.global_graph.add_edge(n2.id, n1.id, "ALIASES", 0.9)

    def _strip_comments(self, text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        text = re.sub(r"//.*", "", text)
        return text
