#include <openssl/evp.h>

// The key is defined through a macro.
#define FIXED_KEY "macro-secret-key"

void macro_encryption(void *ctx) {
    // The macro value becomes key material.
    const char *key = FIXED_KEY;

    // The key reaches the real crypto API.
    EVP_EncryptInit_ex(
        ctx,
        EVP_aes_128_cbc(),
        0,
        key,
        0
    );
}