// Macro variant 1 - VULNERABLE
#define RAW_KEY_1 "macro_secret_1"
#define ENCRYPT_CALL_1(k) AES_set_encrypt_key(k, 256, NULL)

void execute_macro_1() {
    const char *k = RAW_KEY_1;
    ENCRYPT_CALL_1(k);
}
