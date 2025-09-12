# ide/app.py
from flask import Flask, render_template, request, send_from_directory
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Driver import parse_text
from antlr4.tree.Trees import Trees

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    image_url = None

    if request.method == "POST":
        code = request.form.get("code", "")
        try:
            image_path = parse_text(code)  # genera el PNG
            result = "Parser OK ✅"
            # Solo guardamos el nombre del archivo para el template
            image_url = "/static_result/" + os.path.basename(image_path)
        except Exception as e:
            result = f"Parser/Runtime error: {e}"

    return render_template("index.html", result=result, image_url=image_url)

# Servir parse_tree.png desde el directorio padre (donde se genera)
@app.route("/static_result/<filename>")
def static_result(filename):
    return send_from_directory(PARENT_DIR, filename)

if __name__ == "__main__":
    # Flask corre en 0.0.0.0 para ser accesible desde fuera del contenedor
    app.run(host="0.0.0.0", port=5000, debug=True)