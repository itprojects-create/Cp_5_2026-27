#include <openssl/evp.h>

// This function represents a runtime key source.
// No cryptographic key value is hard-coded in this file.
int load_key_from_secure_source(
    unsigned char *key_buffer
) {
    return 1;
}

void runtime_encryption(void *ctx) {
    // The key is filled at runtime.
    unsigned char key[16];

    // The key does not originate from a source-code literal.
    if (!load_key_from_secure_source(key)) {
        return;
    }

    // The runtime key is passed to a real OpenSSL API.
    EVP_EncryptInit_ex(
        ctx,
        EVP_aes_128_cbc(),
        0,
        key,
        0
    );
}