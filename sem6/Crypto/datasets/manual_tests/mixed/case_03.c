// Mixed variant 3 - VULNERABLE
#define BASE_KEY_3 "mixed_key_3"

struct CryptoConfig_3 {
    char *key_data;
};

void run_mixed_3() {
    struct CryptoConfig_3 conf;
    conf.key_data = BASE_KEY_3;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
