/**
 * Intentionally Vulnerable Target Binary for Fuzz Testing
 * ========================================================
 * This program contains DELIBERATE vulnerabilities:
 *   1. Stack buffer overflow (strcpy without bounds checking)
 *   2. Format string vulnerability (user-controlled printf)
 *   3. Integer overflow in allocation size calculation
 *   4. Out-of-bounds array access
 *
 * Compile WITHOUT protections:
 *   clang++ -o vulnerable -fno-stack-protector -O0 -g vulnerable.cpp
 *
 * WARNING: FOR EDUCATIONAL / SECURITY RESEARCH USE ONLY.
 */

#include <cstdio>
#include <cstring>
#include <cstdlib>

// VULNERABILITY 1: Stack buffer overflow — no bounds checking on strcpy
void process_name(const char* name) {
    char buffer[64];
    strcpy(buffer, name);  // Overflows if name > 63 chars
    printf("Processing: %s\n", buffer);
}

// VULNERABILITY 2: Format string — user controls the format specifier
void process_format(const char* fmt) {
    printf(fmt);  // Attacker-controlled format string
    printf("\n");
}

// VULNERABILITY 3: Integer overflow in allocation math
void process_count(const char* count_str) {
    int count = atoi(count_str);
    int size = count * 4;  // Wraps on large count values
    if (size > 0) {
        char* buf = (char*)malloc(size);
        if (buf) {
            memset(buf, 'A', count * 4);  // Writes beyond allocation
            free(buf);
        }
    }
}

// VULNERABILITY 4: Out-of-bounds read with unchecked index
void process_index(const char* data, const char* idx_str) {
    int idx = atoi(idx_str);
    char table[16] = {0};
    strncpy(table, data, 15);
    printf("Value at index: %c\n", table[idx]);  // No bounds check
}

int main() {
    char input[4096];
    size_t total = 0;

    // Read all of stdin into buffer
    while (total < sizeof(input) - 1) {
        int c = fgetc(stdin);
        if (c == EOF) break;
        input[total++] = (char)c;
    }
    input[total] = '\0';

    if (total == 0) return 0;

    // Parse key=value lines
    char* line = strtok(input, "\n");
    char* last_data = nullptr;

    while (line) {
        char* eq = strchr(line, '=');
        if (eq) {
            *eq = '\0';
            char* key   = line;
            char* value = eq + 1;

            if      (strcmp(key, "name")   == 0) process_name(value);
            else if (strcmp(key, "format") == 0) process_format(value);
            else if (strcmp(key, "count")  == 0) process_count(value);
            else if (strcmp(key, "index")  == 0 && last_data) process_index(last_data, value);
            else if (strcmp(key, "data")   == 0) last_data = value;
        }
        line = strtok(nullptr, "\n");
    }

    return 0;
}
