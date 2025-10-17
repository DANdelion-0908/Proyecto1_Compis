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
    symbol_table = None
    intermediate_code = None

    if request.method == "POST":
        code = request.form.get("code", "")
        try:
            parse_result = parse_text(code)
            
            all_errors = parse_result["syntax_errors"] + parse_result["semantic_errors"]
            
            if all_errors:
                result = {"status": "error", "messages": all_errors}
            else:
                result = {"status": "ok", "messages": ["OK"]}
                symbol_table = parse_result["symbol_table"]
                intermediate_code = parse_result["intermediate_code"]  # 🔹 Capturamos el TAC
            
            image_url = "/static_result/" + os.path.basename(parse_result["image_path"])
            
        except Exception as e:
            result = {"status": "error", "messages": [f"Unexpected error: {e}"]}

    return render_template(
        "index.html", 
        result=result, 
        image_url=image_url, 
        symbol_table=symbol_table, 
        intermediate_code=intermediate_code  # 🔹 Enviamos al HTML
    )


# Servir parse_tree.png desde el directorio padre (donde se genera)
@app.route("/static_result/<filename>")
def static_result(filename):
    return send_from_directory(PARENT_DIR, filename)

if __name__ == "__main__":
    # Flask corre en 0.0.0.0 para ser accesible desde fuera del contenedor
    app.run(host="0.0.0.0", port=5050, debug=True)