class Calculator {
    function add(a: integer, b: integer): integer {
        let result: integer = a + b;
        return result;
    }
}

let calc: Calculator = new Calculator();
let x: integer = 5;
let y: integer = 3;
let sum: integer = calc.add(x, y);
