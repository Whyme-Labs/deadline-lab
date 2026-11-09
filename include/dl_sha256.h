#ifndef DL_SHA256_H
#define DL_SHA256_H
#include <stddef.h>
#include <stdint.h>
typedef struct {
  uint32_t h[8];
  uint64_t bytes;
  unsigned char block[64];
  size_t used;
} dl_sha256;
void dl_sha256_init(dl_sha256 *s);
void dl_sha256_update(dl_sha256 *s, const void *data, size_t n);
void dl_sha256_final(dl_sha256 *s, char hex[65]);
/* Hash a bounded regular file without following its final symbolic link. */
int dl_sha256_file(const char *path, char hex[65], size_t *bytes);
#endif
