def matrix_mult(n):
    result = 0
    for i in range(n):
        for j in range(n):
            for k in range(n):
                result += i * j * k
    return result


print(matrix_mult(100))
