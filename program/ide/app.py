# ide/app.py
from flask import Flask, render_template, request
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Driver import parse_text

from antlr4.tree.Trees import Trees

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    code = request.form.get("code", "")
    result = None
    parse_tree = None
    if request.method == "POST":
        try:
            tree, parser = parse_text(code)
            analyzer = ""
            analyzer.visit(tree)
            if analyzer.errors:
                result = {
                    "status": "error",
                    "messages": [str(e) for e in analyzer.errors]
                }
            else:
                result = {"status": "ok", "messages": ["Semantic analysis passed ✅"]}
            parse_tree = Trees.toStringTree(tree, None, parser)
        except Exception as e:
            result = {"status": "error", "messages": [f"Parser/Runtime error: {e}"]}

    return render_template("index.html", code=code, result=result, parse_tree=parse_tree)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

