// Pointer alias variant 7 - VULNERABLE
void alias_flow_7() {
    char *orig_key = "alias_secret_7";
    char *ptr1 = orig_key;
    char *ptr2 = ptr1;
    AES_set_encrypt_key(ptr2, 128, NULL);
}
