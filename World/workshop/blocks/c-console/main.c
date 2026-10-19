/* A menu-driven console program in C. Build and run from the Workshop, or: gcc main.c -o app && ./app */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Read a whole line safely (never more than the buffer holds) and drop the newline. */
static int read_line(const char *prompt, char *buf, size_t size) {
    printf("%s", prompt);
    fflush(stdout);
    if (!fgets(buf, (int)size, stdin)) return 0;
    buf[strcspn(buf, "\r\n")] = '\0';
    return 1;
}

/* Read a whole number, asking again until it is one. Returns 0 at end of input. */
static int read_int(const char *prompt, int *out) {
    char buf[64];
    while (read_line(prompt, buf, sizeof buf)) {
        char *end;
        long v = strtol(buf, &end, 10);
        if (end != buf && *end == '\0') { *out = (int)v; return 1; }
        printf("Please type a whole number.\n");
    }
    return 0;
}

int main(void) {
    int choice;
    printf("== My C program ==\n");
    for (;;) {
        printf("\n1) Say hello\n2) Add two numbers\n0) Quit\n");
        if (!read_int("Choose: ", &choice) || choice == 0) break;
        if (choice == 1) {
            char name[64];
            if (read_line("Your name: ", name, sizeof name)) printf("Hello, %s!\n", name);
        } else if (choice == 2) {
            int a, b;
            if (read_int("First: ", &a) && read_int("Second: ", &b)) printf("%d + %d = %d\n", a, b, a + b);
        } else {
            printf("No option %d.\n", choice);
        }
    }
    printf("Bye.\n");
    return 0;
}
