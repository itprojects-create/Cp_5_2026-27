// Macro variant 3 - VULNERABLE
#define RAW_KEY_3 "macro_secret_3"
#define ENCRYPT_CALL_3(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_3() {
    const char *k = RAW_KEY_3;
    ENCRYPT_CALL_3(k);
}
