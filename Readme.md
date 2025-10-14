# MyLang

### Integrantes

- Eunice Mata, 21231
- Héctor Penedo, 22217

### Librerias

Las librerías que utiliza este contenedor son:

- Antlr4
- Flask
- Graphviz

### ¿Cómo iniciar el contenedor?

Windows

```bash
docker build --rm . -t csp-image && docker run --rm -ti -p 5050:5050 -v "%cd%\program":/program csp-image
```

Linux

```bash
docker build --rm . -t csp-image && docker run --rm -ti -p 5050:5050 -v "$(pwd)/program":/program csp-image
```

### Generar y probar el lenguaje

```bash
antlr -Dlanguage=Python3 -visitor Compiscript.g4
python3 Driver.py program.cps
```

## ¿Cómo usar el IDE?

```bash
python3 ide/app.py
```
