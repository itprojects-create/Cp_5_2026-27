// Wrapper variant 4 - CLEAN
#include <stdio.h>
#include <stdlib.h>

void inner_crypto_layer_4(const char *k) {
    AES_set_encrypt_key(k, 128, NULL);
}

void intermediate_wrapper_4(const char *key) {
    inner_crypto_layer_4(key);
}

void service_handler_4() {
    const char *key = getenv("CRYPTO_KEY");
    intermediate_wrapper_4(key);
}
