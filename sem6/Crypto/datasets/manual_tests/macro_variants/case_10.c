// Macro variant 10 - CLEAN
#define RAW_KEY_10 get_runtime_key()
#define ENCRYPT_CALL_10(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_10() {
    const char *k = RAW_KEY_10;
    ENCRYPT_CALL_10(k);
}
