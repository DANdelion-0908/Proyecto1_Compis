import sys
from antlr4 import *
from antlr4.error.ErrorListener import ErrorListener
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from graphviz import Digraph
from Visitor import Visitor
from antlr4 import InputStream

class CustomErrorListener(ErrorListener):
    def __init__(self):
        self.errors = []
    
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.errors.append(f"line {line}:{column} {msg}")

def tree_to_graph(tree, rule_names, graph=None, parent=None, count=[0]):
    if graph is None:
        graph = Digraph()
    
    node_id = str(count[0])
    count[0] += 1

    if isinstance(tree, TerminalNode):
        label = tree.getText().replace('"', '\\"')
    else :
        rule_index = tree.getRuleIndex()
        label = rule_names[rule_index]

    graph.node(node_id, label)
    
    if parent is not None:
        graph.edge(parent, node_id)

    if not isinstance(tree, TerminalNode):
        for i in range(tree.getChildCount()):
            child = tree.getChild(i)
            tree_to_graph(child, rule_names, graph, node_id, count)

    return graph


def parse_text(code: str):
    input_stream = InputStream(code)
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    
    # Add custom error listener
    error_listener = CustomErrorListener()
    lexer.removeErrorListeners()
    parser.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    parser.addErrorListener(error_listener)
    
    tree = parser.program()
    
    # Get syntax errors
    syntax_errors = error_listener.errors
    
    # Run visitor to get semantic errors and symbol table
    visitor = Visitor()
    visitor.visit(tree)
    semantic_errors = visitor.errors
    
    # Generate parse tree image
    graph = tree_to_graph(tree, parser.ruleNames)
    output_path = "parse_tree" 
    graph.render(output_path, format='png', cleanup=True)
    
    return {
        "syntax_errors": syntax_errors,
        "semantic_errors": semantic_errors,
        "symbol_table": visitor.symbol_table,
        "image_path": output_path + ".png"
    }

def main(argv):
    input_stream = FileStream(argv[1])
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    
    # Add custom error listener for command line
    error_listener = CustomErrorListener()
    lexer.removeErrorListeners()
    parser.removeErrorListeners()
    lexer.addErrorListener(error_listener)
    parser.addErrorListener(error_listener)
    
    tree = parser.program()

    visitor = Visitor()
    visitor.visit(tree)
    
    # Print all errors
    for error in error_listener.errors:
        print(error)
    for error in visitor.errors:
        print(error)

    graph = tree_to_graph(tree, parser.ruleNames)
    graph.render('parse_tree', format='png', cleanup=True)

if __name__ == '__main__':
    main(sys.argv)