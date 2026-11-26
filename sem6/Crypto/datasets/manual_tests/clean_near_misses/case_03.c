// Clean near-miss 3 - CLEAN
// Variable name contains 'key' or 'secret' but is populated dynamically or safely
#include <stdio.h>
#include <stdlib.h>

void safe_crypto_3() {
    char secret_key_buffer[64];
    if (RAND_bytes((unsigned char *)secret_key_buffer, 32) != 1) {
        return;
    }
    AES_set_encrypt_key(secret_key_buffer, 256, NULL);
}
