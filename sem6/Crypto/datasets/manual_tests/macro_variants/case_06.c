// Macro variant 6 - CLEAN
#define RAW_KEY_6 get_runtime_key()
#define ENCRYPT_CALL_6(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_6() {
    const char *k = RAW_KEY_6;
    ENCRYPT_CALL_6(k);
}
