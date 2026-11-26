// Wrapper variant 2 - CLEAN
#include <stdio.h>
#include <stdlib.h>

void inner_crypto_layer_2(const char *k) {
    AES_set_encrypt_key(k, 128, NULL);
}

void intermediate_wrapper_2(const char *key) {
    inner_crypto_layer_2(key);
}

void service_handler_2() {
    const char *key = getenv("CRYPTO_KEY");
    intermediate_wrapper_2(key);
}
