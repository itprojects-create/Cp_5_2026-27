// Mixed variant 9 - VULNERABLE
#define BASE_KEY_9 "mixed_key_9"

struct CryptoConfig_9 {
    char *key_data;
};

void run_mixed_9() {
    struct CryptoConfig_9 conf;
    conf.key_data = BASE_KEY_9;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
