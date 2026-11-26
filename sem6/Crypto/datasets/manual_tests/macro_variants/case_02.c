// Macro variant 2 - CLEAN
#define RAW_KEY_2 get_runtime_key()
#define ENCRYPT_CALL_2(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_2() {
    const char *k = RAW_KEY_2;
    ENCRYPT_CALL_2(k);
}
