// Wrapper variant 7 - VULNERABLE
#include <stdio.h>
#include <stdlib.h>

void inner_crypto_layer_7(const char *k) {
    AES_set_encrypt_key(k, 128, NULL);
}

void intermediate_wrapper_7(const char *key) {
    inner_crypto_layer_7(key);
}

void service_handler_7() {
    const char *key = "hardcoded_key_wrapper_variant";
    intermediate_wrapper_7(key);
}
