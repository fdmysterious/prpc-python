"""
┌────────────────────────────┐
│ Basic PRPC parsing example │
└────────────────────────────┘

 Florian Dupeyron
 April 2022
"""

import prpc

command_simple = "0:hello\n"
command_args   = "0:with_args yes 2.0\n"
command_escaped= r'0:escaped "escaped \"quote\""' + "\n"

if __name__ == "__main__":
    hello = prpc.parse(command_simple)
    print(hello)
    print(repr(hello.encode()))

    args  = prpc.parse(command_args)
    print(args)
    print(repr(args.encode()))

    escaped = prpc.parse(command_escaped)
    print(escaped)
    print(repr(escaped.encode()))

    my_response = prpc.PRPC_Frame(seq_id=0, identifier="ok")
    print(repr(my_response.encode()))
