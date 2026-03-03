#include <stdio.h>
#include <string.h>
#define N 10000
int main(void) {
  char p[N + 1];
  memset(p, 1, sizeof(p));
  p[0] = p[1] = 0;
  for (int i = 2; (long long)i * i <= N; i++)
    if (p[i])
      for (int j = i * i; j <= N; j += i)
        p[j] = 0;
  int c = 0;
  for (int i = 0; i <= N; i++)
    c += p[i];
  printf("%d\n", c);
  return 0;
}
