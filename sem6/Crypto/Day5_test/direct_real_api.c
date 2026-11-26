#include <openssl/evp.h>

// This key is hard-coded directly in the source code.
unsigned char key[16] = {
    0x10, 0x11, 0x12, 0x13,
    0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1A, 0x1B,
    0x1C, 0x1D, 0x1E, 0x1F
};

// This initialization vector is only a test value.
unsigned char iv[16] = {0};

void direct_encryption(void *ctx) {
    // EVP_EncryptInit_ex is a real OpenSSL cryptographic API.
    // The hard-coded key reaches the key argument here.
    EVP_EncryptInit_ex(
        ctx,
        EVP_aes_128_cbc(),
        0,
        key,
        iv
    );
}