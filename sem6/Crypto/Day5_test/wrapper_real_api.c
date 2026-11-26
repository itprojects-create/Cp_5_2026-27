#include <openssl/evp.h>

// This key is hard-coded.
unsigned char key[16] = {
    0x20, 0x21, 0x22, 0x23,
    0x24, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2A, 0x2B,
    0x2C, 0x2D, 0x2E, 0x2F
};

// The key is passed through a wrapper parameter.
void initialize_cipher(
    void *ctx,
    unsigned char *encryption_key
) {
    // The wrapper passes the parameter to the real crypto API.
    EVP_EncryptInit_ex(
        ctx,
        EVP_aes_128_cbc(),
        0,
        encryption_key,
        0
    );
}

void wrapper_encryption(void *ctx) {
    // The hard-coded key enters the wrapper here.
    initialize_cipher(ctx, key);
}