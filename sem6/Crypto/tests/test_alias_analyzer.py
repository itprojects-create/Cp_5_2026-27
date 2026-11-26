import pytest
from External_scanner.alias_analyzer import AliasAnalyzer, PointerAssignment
from External_scanner.flow_tracker import FlowTracker


def test_simple_pointer_alias():
    code = """
char *secret = "password123";
char *ptr = &secret;
"""
    analyzer = AliasAnalyzer()
    assignments = analyzer.find_pointer_assignments(code)
    assert len(assignments) >= 1
    alias_sets = analyzer.build_alias_sets()
    assert analyzer.may_alias("ptr", "secret")
    assert "secret" in analyzer.get_aliases("ptr")


def test_pointer_to_pointer_alias():
    code = """
int *p1 = &val;
int *p2 = p1;
int **p3 = &p2;
"""
    analyzer = AliasAnalyzer()
    analyzer.find_pointer_assignments(code)
    analyzer.build_alias_sets()
    assert analyzer.may_alias("p1", "val")
    assert analyzer.may_alias("p2", "p1")
    assert analyzer.may_alias("p2", "val")


def test_struct_pointer_alias():
    code = """
CryptoConfig config;
CryptoConfig *sptr = &config;
"""
    analyzer = AliasAnalyzer()
    analyzer.find_pointer_assignments(code)
    analyzer.build_alias_sets()
    assert analyzer.may_alias("sptr", "config")


def test_array_pointer_alias():
    code = """
char key_buffer[32];
char *aptr = key_buffer;
"""
    analyzer = AliasAnalyzer()
    analyzer.find_pointer_assignments(code)
    analyzer.build_alias_sets()
    assert analyzer.may_alias("aptr", "key_buffer")


def test_integration_with_flow_tracker():
    tracker = FlowTracker()
    tracker.track_assignment("key1", '"hardcoded_val"', line_number=1)
    tracker.track_assignment("key2", 'clean_source', line_number=2)

    analyzer = AliasAnalyzer()
    code = "char *key1 = key2;"
    analyzer.find_pointer_assignments(code)
    analyzer.integrate_with_flow_tracker(tracker)

    # Check that ALIASES edges were added between key1 and key2
    alias_edges = [e for e in tracker.global_graph.edges if e.edge_type == "ALIASES"]
    assert len(alias_edges) >= 2


class TestAliasAnalyzer:
    def test_simple_pointer_alias(self):
        """Test simple pointer alias: ptr = &var."""
        analyzer = AliasAnalyzer()
        analyzer.add_pointer_assignment("ptr", "var")
        assert analyzer.may_alias("ptr", "var")
        assert "ptr" in analyzer.get_aliases("var")
        assert "var" in analyzer.get_aliases("ptr")

    def test_pointer_to_pointer(self):
        """Test pointer-to-pointer: ptr2 = &ptr1."""
        analyzer = AliasAnalyzer()
        analyzer.add_pointer_assignment("ptr2", "ptr1")
        assert analyzer.may_alias("ptr2", "ptr1")

    def test_transitive_alias(self):
        """Test transitive aliasing: ptr1 = &var, ptr2 = ptr1."""
        analyzer = AliasAnalyzer()
        analyzer.add_pointer_assignment("ptr1", "var")
        analyzer.add_pointer_copy("ptr2", "ptr1")
        assert analyzer.may_alias("ptr2", "var")
        assert "var" in analyzer.get_aliases("ptr2")

    def test_parse_assignments(self):
        """Test parsing pointer assignments from code."""
        analyzer = AliasAnalyzer()
        code = """
        char *ptr = &buffer;
        char *ptr2 = ptr;
        """
        assignments = analyzer.parse_pointer_assignments(code)
        assert len(assignments) >= 1
        assert analyzer.may_alias("ptr", "buffer")

