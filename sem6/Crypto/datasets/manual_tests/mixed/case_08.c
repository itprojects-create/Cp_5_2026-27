// Mixed variant 8 - CLEAN
#define BASE_KEY_8 load_key_from_vault()

struct CryptoConfig_8 {
    char *key_data;
};

void run_mixed_8() {
    struct CryptoConfig_8 conf;
    conf.key_data = BASE_KEY_8;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
