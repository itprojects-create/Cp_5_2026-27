import pytest
from External_scanner.macro_expander import MacroExpander, MacroDefinition


def test_simple_object_macro():
    code = """
#define KEY_SIZE 256
int size = KEY_SIZE;
"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert "KEY_SIZE" in expander.macros
    assert expander.macros["KEY_SIZE"].body == "256"
    assert "int size = 256;" in expanded


def test_function_like_macro():
    code = """
#define ENCRYPT(d, k) aes_encrypt(d, k)
void run() {
    ENCRYPT(data_buf, secret_key);
}
"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert "aes_encrypt(data_buf, secret_key);" in expanded


def test_nested_macro_expansion():
    code = """
#define A 128
#define B A
#define C B
int key_len = C;
"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert "int key_len = 128;" in expanded
    assert expander.expand_token("C") == "128"


def test_multiline_macro_with_backslash():
    code = """
#define INIT_CRYPTO(ctx, key) \\
    setup_context(ctx); \\
    load_key(ctx, key);

void run() {
    INIT_CRYPTO(my_ctx, "hardcoded_key");
}
"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert "setup_context(my_ctx);" in expanded
    assert 'load_key(my_ctx, "hardcoded_key");' in expanded


def test_macro_in_string_literal_and_comments():
    code = """
#define SECRET "password123"
// Do not replace SECRET in this comment
char *msg = "This is a SECRET key";
char *real_key = SECRET;
"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert '"This is a SECRET key"' in expanded
    assert '// Do not replace SECRET in this comment' in expanded
    assert 'char *real_key = "password123";' in expanded


def test_line_number_preservation():
    code = """line 1
#define VALUE 42
line 3
int x = VALUE;
line 5"""
    expander = MacroExpander()
    expanded = expander.expand(code)
    assert expanded.splitlines()[3] == "int x = 42;"
    assert len(expanded.splitlines()) == len(code.splitlines())


class TestMacroExpander:
    def test_object_like_macro(self):
        """Test simple object-like macro expansion."""
        expander = MacroExpander()
        code = """
        #define KEY_SIZE 256
        char buffer[KEY_SIZE];
        """
        expanded = expander.expand(code)
        assert "char buffer[256];" in expanded
        assert "KEY_SIZE" not in expanded

    def test_function_like_macro(self):
        """Test function-like macro with parameters."""
        expander = MacroExpander()
        code = """
        #define ENCRYPT(data, key) encrypt_data(data, key)
        ENCRYPT(buffer, my_key);
        """
        expanded = expander.expand(code)
        assert "encrypt_data(buffer, my_key);" in expanded
        assert "ENCRYPT" not in expanded

    def test_nested_macro(self):
        """Test nested macro expansion (A -> B -> C)."""
        expander = MacroExpander()
        code = """
        #define A B
        #define B C
        #define C 123
        int x = A;
        """
        expanded = expander.expand(code)
        assert "int x = 123;" in expanded
        assert "A" not in expanded
        assert "B" not in expanded

    def test_macro_in_string_literal(self):
        """Test that macros in string literals are NOT expanded."""
        expander = MacroExpander()
        code = """
        #define KEY 123
        printf("KEY should not expand");
        """
        expanded = expander.expand(code)
        assert '"KEY should not expand"' in expanded

    def test_multiline_macro(self):
        """Test multi-line macro with backslash."""
        expander = MacroExpander()
        code = """
        #define MULTI_LINE \\
            statement1; \\
            statement2;
        MULTI_LINE
        """
        expanded = expander.expand(code)
        assert "statement1;" in expanded
        assert "statement2;" in expanded

