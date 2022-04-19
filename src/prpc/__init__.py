"""
┌────────────────────────────┐
│ Simple python PRPC wrapper │
└────────────────────────────┘

 Florian Dupeyron
 April 2022

 a PRPC message is a simple message containing a sequence index,
 a command identifier, and optionally some args. For example :

    - 0:hello
    - 0:copy stuff

 PRPC messages strings must be terminated by a newline character (\n).

 like json-rpc, PRPC supports 'notifications', i.e. messages without requests,
 by having a sequence index of '*'. For example:

    - *:gpio/my_gpio/value/change yes

 note that slashes are supported for command identifiers. This allow a hierarchical
 organization of commands, which is compatible to interface for example with a MQTT
 broker afterwards.

 Supported arguments types are:

    - int: 3, -203
    - float: 2.0, -3.40; Please note that even if there is no decimal part, .0 must be supplied.
    - bool: yes for true, no for False
    - string: "this is a string with an escaped \"quote\"".
"""

import timeit
import json

from pathlib                  import Path
from functools                import reduce
from dataclasses              import dataclass, field
from typing                   import Tuple

from parsimonious.grammar     import Grammar
from parsimonious.nodes       import NodeVisitor

from parsimonious.exceptions  import (
    ParseError,
    VisitationError
)


# ┌────────────────────────────────────────┐
# │ PRPC Frame dataclass                   │
# └────────────────────────────────────────┘

@dataclass
class PRPC_Frame:
    seq_id: int
    identifier: str
    args: Tuple[any] = None

    # ────────── Various predicates ────────── #
    
    def is_response(self):
        return self.identifier in ("ok", "result", "error")


    # ──────────────── Encode ──────────────── #
    
    def encode(self):
        def proc_arg(a):
            # WARNING # isinstance(True|False, int) == True :'(
            # So bool condition must be before int condition.

            if isinstance(a, bool):
                return "yes" if a else "no"
            elif isinstance(a, float):
                a_str = f"{a:f}"
                return a_str
            elif isinstance(a, int):
                return str(a)
            elif isinstance(a, str):
                escaped = a.replace('"', '\\"')
                return f'"{escaped}"'
            else:
                raise RuntimeError(f"Uknown arg of type {type(a)}: {a}")

        id_str   = "*" if self.seq_id is None else str(self.seq_id)
        args_str = ""
        if self.args is not None:
            args_str = " " + " ".join(map(lambda x: proc_arg(x), self.args))

        return f"{id_str}:{self.identifier}{args_str}\n"


# ┌────────────────────────────────────────┐
# │ Parsimonious grammar                   │
# └────────────────────────────────────────┘

rules_txt = ((Path(__file__) / "..").resolve() / "rules.peg").read_text()
grammar   = Grammar(rules_txt)


# ┌────────────────────────────────────────┐
# │ Parsimonious node visitor              │
# └────────────────────────────────────────┘

class PRPC_NodeVisitor(NodeVisitor):
    # Visit command
    def visit_command(self, node, visited_children):
        idx, _, identifier, args, *_ = visited_children

        return PRPC_Frame(
            seq_id     = idx,
            identifier = identifier,
            args       = None if not args else args[0]
        )

    # Visit args
    def visit_args(self, node, visited_children):
        if len(visited_children) >= 2:
            return (visited_children[0], *visited_children[1])
        else:
            return tuple(visited_children[0])

    def visit_arg(self, node, visited_children):
        _, value = visited_children
        return value

    def visit_arg_value(self, node, visited_children):
        return visited_children[0] # Contains argument value

    # Visit scalar types
    def visit_bool(self, node, visited_children):
        if   node.text == "yes": return True
        elif node.text == "no":  return False
        else: return None

    def visit_int(self, node, visited_children):
        return int(node.text)

    def visit_float(self, node, visited_childre):
        return float(node.text)

    def visit_str(self, node, visited_children):
        # Trim start and end ", replace \" with "
        return node.text[1:-1].replace('\\"', '"')

    # Identifiers
    def visit_id(self, node, visited_children):
        if node.text == "*": return None
        else:                return int(node.text)
    
    def visit_identifier(self, node, visited_children):
        return node.text

    # Ignored nodes
    def visit_sep(self, node, visited_children):
        pass
    def visit_eol(self, node, visited_children):
        pass
    def visit_wh(self, node, visited_children):
        pass

    # generic visit
    def generic_visit(self, node, visited_children):
        return visited_children

visitor = PRPC_NodeVisitor()


# ┌────────────────────────────────────────┐
# │ Parse function                         │
# └────────────────────────────────────────┘

def parse(msg: str):
    return visitor.visit(grammar.parse(msg))
