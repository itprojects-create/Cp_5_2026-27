// Macro variant 8 - CLEAN
#define RAW_KEY_8 get_runtime_key()
#define ENCRYPT_CALL_8(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_8() {
    const char *k = RAW_KEY_8;
    ENCRYPT_CALL_8(k);
}
