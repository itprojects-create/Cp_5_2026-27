// Mixed variant 5 - VULNERABLE
#define BASE_KEY_5 "mixed_key_5"

struct CryptoConfig_5 {
    char *key_data;
};

void run_mixed_5() {
    struct CryptoConfig_5 conf;
    conf.key_data = BASE_KEY_5;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
