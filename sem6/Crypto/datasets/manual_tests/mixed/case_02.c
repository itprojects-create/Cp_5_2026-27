// Mixed variant 2 - CLEAN
#define BASE_KEY_2 load_key_from_vault()

struct CryptoConfig_2 {
    char *key_data;
};

void run_mixed_2() {
    struct CryptoConfig_2 conf;
    conf.key_data = BASE_KEY_2;
    char *ptr = conf.key_data;
    AES_set_encrypt_key(ptr, 128, NULL);
}
