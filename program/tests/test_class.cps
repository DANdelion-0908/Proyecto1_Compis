class Point {
    let x: integer = 0;
    let y: integer = 0;

    function getX(): integer {
        return x;
    }

    function setX(newX: integer): void {
        x = newX;
    }
}

let p: Point = new Point();
