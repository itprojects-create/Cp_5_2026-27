// Mixed variant 1 - VULNERABLE
#define BASE_KEY_1 "mixed_key_1"

struct CryptoConfig_1 {
    char *key_data;
};

void run_mixed_1() {
    struct CryptoConfig_1 conf;
    conf.key_data = BASE_KEY_1;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
