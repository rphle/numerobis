#include <stdio.h>
int main(void) {
  long long r = 0;
  int n = 100;
  for (int i = 0; i < n; i++)
    for (int j = 0; j < n; j++)
      for (int k = 0; k < n; k++)
        r += (long long)i * j * k;
  printf("%lld\n", r);
  return 0;
}
