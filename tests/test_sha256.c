#include "dl_sha256.h"
#include <stdio.h>
#include <string.h>
int main(void) {
  const char *input[] = {
      "", "abc", "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"};
  const char *expected[] = {
      "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"};
  for (int i = 0; i < 3; i++) {
    dl_sha256 s;
    char out[65];
    dl_sha256_init(&s);
    for (size_t j = 0; j < strlen(input[i]); j++)
      dl_sha256_update(&s, input[i] + j, 1);
    dl_sha256_final(&s, out);
    if (strcmp(out, expected[i]))
      return 1;
  }
  dl_sha256 s;
  char out[65];
  dl_sha256_init(&s);
  for (int i = 0; i < 1000000; i++)
    dl_sha256_update(&s, "a", 1);
  dl_sha256_final(&s, out);
  if (strcmp(
          out,
          "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"))
    return 1;
  puts("4 SHA-256 known-answer vectors passed");
  return 0;
}
