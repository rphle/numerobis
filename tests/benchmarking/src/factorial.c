#include <stdio.h>
int main(void) {
  unsigned long long r = 1;
  for (int i = 2; i <= 20; i++)
    r *= i;
  printf("%llu\n", r);
  return 0;
}
