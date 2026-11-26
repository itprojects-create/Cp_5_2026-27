// Macro variant 9 - VULNERABLE
#define RAW_KEY_9 "macro_secret_9"
#define ENCRYPT_CALL_9(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_9() {
    const char *k = RAW_KEY_9;
    ENCRYPT_CALL_9(k);
}
