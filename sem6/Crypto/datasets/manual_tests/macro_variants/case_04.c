// Macro variant 4 - CLEAN
#define RAW_KEY_4 get_runtime_key()
#define ENCRYPT_CALL_4(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_4() {
    const char *k = RAW_KEY_4;
    ENCRYPT_CALL_4(k);
}
