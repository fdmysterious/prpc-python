"""
┌─────────────────────────────────────────┐
│ Device com. helper around TextIOWrapper │
└─────────────────────────────────────────┘

 Florian Dupeyron
 April 2022
"""

import io
import serial
import threading
import traceback

import prpc

import queue
import collections

class PRPC_Request:
    def __init__(self, handler: "PRPC_Handler"):
        self.handler = handler
        self.result  = queue.Queue(1) # Result value

    def wait(self, timeout=None):
        return self.result.get(timeout=timeout)

    ## TODO abort? ##

class PRPC_IOHandler:
    """
    This class is a helper that allows to handle a communication
    device (i.e. a serial port or a socket) to handle PRPC messages.

    reception is done in a separate thread to manage asynchronous events
    without asyncio flavor. It is assumed that the resulting code will
    be more resilient that way, especially when mixed with other communication
    interfaces coming from third-party contributors, that doesn't always
    generate the best python-friendly code. Oopsie gloopsie!
    """

    def __init__(self, io_: io.IOBase, max_reqs=1024):
        self.io             = io_
        self.rx_worker      = threading.Thread(target=self._rx_worker, daemon=True)
        self.started        = threading.Event()

        self.req_lock       = threading.RLock()
        self.reqs           = [None]*max_reqs
        self.available_ids  = collections.deque(range(max_reqs))


    # ───────────── Start / Stop ───────────── #

    def start(self):
        self.started.set()
        self.rx_worker.start()

    def stop(self):
        self.started.clear()
        self.rx_worker.join(timeout=10)


    # ───────────── ID managment ───────────── #
    
    def _id_get(self):
        return self.available_ids.pop()

    def _id_free(self, id_):
        self.available_ids.append(id_)


    # ──────────── Request message ─────────── #

    def req(self, identifier, *args):
        # Assign seq id
        seq_id = self._id_get()


        # Build frame
        frame = prpc.PRPC_Frame(
            seq_id     = seq_id,
            identifier = identifier,
            args       = args
        )


        # Build request object
        rq = PRPC_Request(self)
        with self.req_lock:
            if self.reqs[frame.seq_id] is not None:
                raise ValueError("Frame seq. id {frame.seq_id} is already waiting for a response")

            else:
                # Send frame
                self.io.write(frame.encode().encode("ascii"))
                self.io.flush()

                # Enqueue frame
                self.reqs[frame.seq_id] = rq
                return rq


    # ─────────────── RX worker ────────────── #

    def _dispatch(self, frame):
        # Frame is a response
        if frame.is_response():
            with self.req_lock:
                if frame.seq_id >= len(self.reqs):
                    pass
                    # TODO ERROR seq id is above limit

                elif self.reqs[frame.seq_id] is not None:
                    req = self.reqs[frame.seq_id]
                    self.reqs[frame.seq_id] = None # Slot is free!
                    req.result.put(frame)
                    self._id_free(frame.seq_id)

                else:
                    pass # TODO # Warning received for uknown request with ID ...

        # Frame is a request
        else:
            pass # TODO # Handle requests

    def _process_line(self, line):
        print("Received line: ", repr(line))
        try:
            frame = prpc.parse(line)
            print(f"→ Received PRPC message: {frame.identifier}")
            self._dispatch(frame)

        except prpc.ParseError as exc:
            print("Failed to parse message", exc)
            traceback.print_exc()
    
    def _rx_worker(self):
        line_buffer = ""

        print("Started RX worker")
        while self.started.is_set():
            # Read a character and append it to input string buffer
            rbuf = self.io.read(1)
            try:
                line_buffer += rbuf.decode("ascii")
            except UnicodeDecodeError as e:
                # todo debug message #
                traceback.print_exc()

            # Find newline characters
            nidx = line_buffer.find("\n")
            while nidx >= 0:
                line = line_buffer[:nidx+1]
                if line:
                    self._process_line(line)
                line_buffer = line_buffer[nidx+1:]
                nidx = line_buffer.find("\n")

        print("Stopped RX worker")
