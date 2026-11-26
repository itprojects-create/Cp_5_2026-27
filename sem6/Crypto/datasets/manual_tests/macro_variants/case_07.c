// Macro variant 7 - VULNERABLE
#define RAW_KEY_7 "macro_secret_7"
#define ENCRYPT_CALL_7(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_7() {
    const char *k = RAW_KEY_7;
    ENCRYPT_CALL_7(k);
}
