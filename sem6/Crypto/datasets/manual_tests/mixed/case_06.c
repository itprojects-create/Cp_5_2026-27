// Mixed variant 6 - CLEAN
#define BASE_KEY_6 load_key_from_vault()

struct CryptoConfig_6 {
    char *key_data;
};

void run_mixed_6() {
    struct CryptoConfig_6 conf;
    conf.key_data = BASE_KEY_6;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
