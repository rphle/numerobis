def sieve(n):
    primes = bytearray([1]) * (n + 1)
    primes[0] = primes[1] = 0
    i = 2
    while i * i <= n:
        if primes[i]:
            primes[i * i :: i] = bytearray(len(primes[i * i :: i]))
        i += 1
    print(sum(primes))


sieve(10000)
