// Macro variant 5 - VULNERABLE
#define RAW_KEY_5 "macro_secret_5"
#define ENCRYPT_CALL_5(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_5() {
    const char *k = RAW_KEY_5;
    ENCRYPT_CALL_5(k);
}
