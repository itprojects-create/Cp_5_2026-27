#include <stdio.h>

// This value is hard-coded but is not cryptographic key material.
const char *message = "encryption started";

void log_message(void) {
    // The value only reaches a logging operation.
    printf("%s\n", message);
}