// Mixed variant 7 - VULNERABLE
#define BASE_KEY_7 "mixed_key_7"

struct CryptoConfig_7 {
    char *key_data;
};

void run_mixed_7() {
    struct CryptoConfig_7 conf;
    conf.key_data = BASE_KEY_7;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
