// Pointer alias variant 2 - CLEAN
void alias_flow_2() {
    char *orig_key = read_secure_token();
    char *ptr1 = orig_key;
    char *ptr2 = ptr1;
    AES_set_encrypt_key(ptr2, 128, NULL);
}
