function fibonacci(n: integer): integer {
  if (n <= 1) {
    return n;
  }
  let a: integer = fibonacci(n - 1);
  let b: integer = fibonacci(n - 2);
  let r: integer = a + b;
  return r;
}