// Wrapper variant 8 - CLEAN
#include <stdio.h>
#include <stdlib.h>

void inner_crypto_layer_8(const char *k) {
    AES_set_encrypt_key(k, 128, NULL);
}

void intermediate_wrapper_8(const char *key) {
    inner_crypto_layer_8(key);
}

void service_handler_8() {
    const char *key = getenv("CRYPTO_KEY");
    intermediate_wrapper_8(key);
}
