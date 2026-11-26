// Wrapper variant 3 - VULNERABLE
#include <stdio.h>
#include <stdlib.h>

void inner_crypto_layer_3(const char *k) {
    AES_set_encrypt_key(k, 128, NULL);
}

void intermediate_wrapper_3(const char *key) {
    inner_crypto_layer_3(key);
}

void service_handler_3() {
    const char *key = "hardcoded_key_wrapper_variant";
    intermediate_wrapper_3(key);
}
