// Mixed variant 10 - CLEAN
#define BASE_KEY_10 load_key_from_vault()

struct CryptoConfig_10 {
    char *key_data;
};

void run_mixed_10() {
    struct CryptoConfig_10 conf;
    conf.key_data = BASE_KEY_10;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
