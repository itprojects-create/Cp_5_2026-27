// Pointer alias variant 8 - CLEAN
void alias_flow_8() {
    char *orig_key = read_secure_token();
    char *ptr1 = orig_key;
    char *ptr2 = ptr1;
    AES_set_encrypt_key(ptr2, 128, NULL);
}
