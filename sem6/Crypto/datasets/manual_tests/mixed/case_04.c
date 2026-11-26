// Mixed variant 4 - CLEAN
#define BASE_KEY_4 load_key_from_vault()

struct CryptoConfig_4 {
    char *key_data;
};

void run_mixed_4() {
    struct CryptoConfig_4 conf;
    conf.key_data = BASE_KEY_4;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
