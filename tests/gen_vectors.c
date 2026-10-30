/*
 * Generates reference vectors from the original passwdqc_random() by
 * replacing its /dev/urandom read with bytes we choose.
 *
 * Build: cc -I../passwdqc -o gen_vectors gen_vectors.c \
 *        ../passwdqc/wordset_4k.c ../passwdqc/passwdqc_memzero.c
 * Output: "bits hex-random passphrase-or-NULL" per line, on stdout.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>

static unsigned char fake_rnd[24];

static ssize_t fake_read(void *buf, size_t count)
{
	if (count > sizeof(fake_rnd))
		count = sizeof(fake_rnd);
	memcpy(buf, fake_rnd, count);
	return count;
}

#define open(path, flags) 3
#define read(fd, buf, count) fake_read(buf, count)
#define close(fd) 0
#include "passwdqc_random.c"
#undef open
#undef read
#undef close

int main(void)
{
	passwdqc_params_qc_t params;
	int bits, trial, i;
	FILE *urandom = fopen("/dev/urandom", "rb");

	if (!urandom)
		return 1;
	memset(&params, 0, sizeof(params));
	params.max = 256;

	for (bits = 20; bits <= 140; bits++)
		for (trial = 0; trial < 50; trial++) {
			if (fread(fake_rnd, sizeof(fake_rnd), 1, urandom) != 1)
				return 1;
			if (trial < 2)
				memset(fake_rnd, trial ? 0xff : 0x00, sizeof(fake_rnd));
			params.random_bits = bits;
			char *pass = passwdqc_random(&params);
			printf("%d ", bits);
			for (i = 0; i < (int)sizeof(fake_rnd); i++)
				printf("%02x", fake_rnd[i]);
			printf(" %s\n", pass ? pass : "NULL");
			free(pass);
		}

	fclose(urandom);
	return 0;
}
