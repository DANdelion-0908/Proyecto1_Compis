import sys
from antlr4 import *
from CompiscriptLexer import CompiscriptLexer
from CompiscriptParser import CompiscriptParser
from graphviz import Digraph
from Visitor import Visitor

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

def parse_text(text: str):
    input_stream = InputStream(text)
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    tree = parser.program()

    graph = tree_to_graph(tree, parser.ruleNames)
    graph.render('parse_tree', format='png', cleanup=True)

    return "Parse successful"

def main(argv):
    input_stream = FileStream(argv[1])
    lexer = CompiscriptLexer(input_stream)
    stream = CommonTokenStream(lexer)
    parser = CompiscriptParser(stream)
    tree = parser.program()  # We are using 'prog' since this is the starting rule based on our Compiscript grammar, yay!

    visitor = Visitor()
    visitor.visit(tree)

    graph = tree_to_graph(tree, parser.ruleNames)
    graph.render('parse_tree', format='png', cleanup=True)

if __name__ == '__main__':
    main(sys.argv)