=============================
Simple python parser for PRPC
=============================

:Authors:   - Florian Dupeyron <florian.dupeyron@mugcat.fr>
:Date:     April 2022

This library provides classes to handle PRPC_ messages. The parser is based
on parsimonious_.

.. _PRPC: https://github.com/fdmysterious/PRPC
.. _parsimonious: https://github.com/erikrose/parsimonious

Basic example
=============

.. code:: python

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

Expected output:

.. code::

    (.env) 
    $ ~/workspace/prpc-python  
    > PYTHONPATH=$PYTHONPATH:$(pwd)
    (.env) 
    $ ~/workspace/prpc-python  
    > python3 examples/basic_parsing.py 
    PRPC_Frame(seq_id=0, identifier='hello', args=None)
    '0:hello\n'
    PRPC_Frame(seq_id=0, identifier='with_args', args=(True, 2.0))
    '0:with_args True 2.0\n'
    PRPC_Frame(seq_id=0, identifier='escaped', args=('escaped "quote"',))
    '0:escaped "escaped \\"quote\\""\n'
    '0:ok\n'
