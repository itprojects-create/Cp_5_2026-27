// Pointer alias variant 1 - VULNERABLE
void alias_flow_1() {
    char *orig_key = "alias_secret_1";
    char *ptr1 = orig_key;
    char *ptr2 = ptr1;
    AES_set_encrypt_key(ptr2, 128, NULL);
}
