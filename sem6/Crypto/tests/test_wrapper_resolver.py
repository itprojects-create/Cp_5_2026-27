import pytest
from External_scanner.wrapper_resolver import WrapperResolver, Call


def test_single_level_wrapper():
    code = """
void my_encrypt_wrapper(const char *key, unsigned char *data) {
    AES_set_encrypt_key(key, 128, data);
}
"""
    resolver = WrapperResolver()
    wrappers = resolver.find_wrappers(code)
    assert len(wrappers) == 1
    w = wrappers[0]
    assert w.name == "my_encrypt_wrapper"
    assert w.target_crypto_api == "AES_set_encrypt_key"
    assert w.depth == 1
    assert w.chain == ["my_encrypt_wrapper", "AES_set_encrypt_key"]
    assert 0 in w.param_to_crypto_arg  # key maps to first arg of AES_set_encrypt_key


def test_multi_level_transitive_wrapper():
    code = """
void low_level_crypto(char *k, char *d) {
    EVP_EncryptInit_ex(ctx, cipher, NULL, k, iv);
}

void high_level_crypto(char *user_key, char *user_data) {
    low_level_crypto(user_key, user_data);
}
"""
    resolver = WrapperResolver()
    wrappers = resolver.find_wrappers(code)
    wrapper_dict = {w.name: w for w in wrappers}
    assert "low_level_crypto" in wrapper_dict
    assert "high_level_crypto" in wrapper_dict
    assert wrapper_dict["high_level_crypto"].depth == 2
    assert wrapper_dict["high_level_crypto"].chain == [
        "high_level_crypto",
        "low_level_crypto",
        "EVP_EncryptInit_ex",
    ]


def test_wrapper_with_multiple_parameters_and_arg_mapping():
    code = """
void custom_cipher(char *k, int mode, char *iv, char *payload) {
    CryptDeriveKey(hProv, Algid, hBaseData, flags, phKey);
}
"""
    resolver = WrapperResolver(crypto_apis={"CryptDeriveKey"})
    wrappers = resolver.find_wrappers(code)
    assert len(wrappers) == 1
    call = Call(
        callee_name="custom_cipher",
        arguments=["hardcoded_key", "1", "null_iv", "buffer"],
    )
    mapping = resolver.map_arguments(call, wrappers[0])
    assert mapping.target_api == "CryptDeriveKey"
    assert mapping.caller_args[0] == "hardcoded_key"


def test_wrapper_returning_crypto_value():
    code = """
int encrypt_and_return_status(char *key, char *in) {
    int res = CryptEncrypt(hKey, 0, 1, 0, pbData, pdwDataLen, dwBufLen);
    return res;
}
"""
    resolver = WrapperResolver()
    wrappers = resolver.find_wrappers(code)
    assert len(wrappers) == 1
    assert wrappers[0].returns_crypto_val is True


def test_non_wrapper_function_ignored():
    code = """
int compute_sum(int a, int b) {
    int sum = a + b;
    printf("Sum: %d\\n", sum);
    return sum;
}
"""
    resolver = WrapperResolver()
    wrappers = resolver.find_wrappers(code)
    assert len(wrappers) == 0


class TestWrapperResolver:
    def test_extract_function(self):
        """Test function extraction from code."""
        resolver = WrapperResolver()
        code = """
        void encrypt_data(char *data, char *key) {
            EVP_EncryptInit_ex(ctx, cipher, key);
        }
        """
        functions = resolver.extract_functions(code, "test.c")
        assert len(functions) == 1
        assert functions[0].name == "encrypt_data"
        assert functions[0].parameters == ["data", "key"]

    def test_find_wrapper(self):
        """Test wrapper function detection."""
        resolver = WrapperResolver()
        code = """
        void encrypt_data(char *data, char *key) {
            EVP_EncryptInit_ex(ctx, cipher, key);
        }
        """
        functions = resolver.extract_functions(code, "test.c")
        wrappers = resolver.find_wrappers(functions)
        assert len(wrappers) == 1
        assert "EVP_EncryptInit_ex" in wrappers[0].crypto_calls

    def test_build_call_graph(self):
        """Test call graph construction."""
        resolver = WrapperResolver()
        code = """
        void crypto_api() { }
        void wrapper() { crypto_api(); }
        void main() { wrapper(); }
        """
        functions = resolver.extract_functions(code, "test.c")
        call_graph = resolver.build_call_graph(functions)
        assert "wrapper" in call_graph["main"]
        assert "crypto_api" in call_graph["wrapper"]

    def test_transitive_wrapper(self):
        """Test transitive wrapper chain resolution."""
        resolver = WrapperResolver()
        code = """
        void EVP_EncryptInit_ex() { }
        void init_cipher() { EVP_EncryptInit_ex(); }
        void encrypt_data() { init_cipher(); }
        """
        functions = resolver.extract_functions(code, "test.c")
        resolver.find_wrappers(functions)
        resolver.build_call_graph(functions)

        chain = resolver.resolve_transitive_wrappers("encrypt_data")
        assert "init_cipher" in chain
        assert "EVP_EncryptInit_ex" in chain

    def test_argument_mapping(self):
        """Test caller argument to callee parameter mapping."""
        resolver = WrapperResolver()
        code = """
        void callee(char *key) { }
        void caller() { callee(my_key); }
        """
        functions = resolver.extract_functions(code, "test.c")
        mapping = resolver.map_arguments("caller", "callee")
        assert mapping is not None
        assert 0 in mapping.argument_to_param

