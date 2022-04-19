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
import logging

import prpc

import queue
import collections

from typing import Callable


# ┌────────────────────────────────────────┐
# │ Errors                                 │
# └────────────────────────────────────────┘

class Request_Aborted(Exception):
    def __init__(self):
        super().__init__("Request aborted")


class Request_Failed(Exception):
    def __init__(self, msg):
        super().__init__(f"Request failed: {msg}")


# ┌────────────────────────────────────────┐
# │ Request object                         │
# └────────────────────────────────────────┘

class PRPC_Request:
    def __init__(self, handler: "PRPC_Handler", abort_callback: Callable[["PRPC_Request"],None]):
        self.handler        = handler
        self.result         = queue.Queue(1) # Result value
        
        self.abort_callback = abort_callback

    def wait(self, timeout=None):
        try:
            result = self.result.get(timeout=timeout)
            if   result            == None:    raise Request_Aborted()
            elif result.identifier == "error": raise Request_Failed(result.args[0])
            elif result.identifier == "result":
                return tuple(result.args)
            else:
                return None # For OK results, return nothing. If an error has occured, an exception has been thrown.

        except queue.Empty:
            self.abort_callback(self)
            raise TimeoutError(f"Timeout waiting response for request")

    def abort(self):
        self.result.put_nowait(None) # Unlock any listening stuff
        self.abort_callback()        # Clear request from handler

    ## TODO abort ##


# ┌────────────────────────────────────────┐
# │ IOHandler                              │
# └────────────────────────────────────────┘

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

    def __init__(self, io_: io.IOBase, max_reqs=1024, encoding="utf-8", logname="PRPC_IOHandler"):
        self.log            = logging.getLogger(logname)
        self.encoding       = encoding

        self.io             = io_
        self.rx_worker      = threading.Thread(target=self._rx_worker, daemon=True)
        self.started        = threading.Event()

        self.req_lock       = threading.RLock()
        self.reqs           = [None]*max_reqs
        self.available_ids  = collections.deque(range(max_reqs))


    # ───────────── Start / Stop ───────────── #

    def start(self):
        self.log.debug("Start RX worker")
        self.started.set()
        self.rx_worker.start()


    def stop(self):
        self.log.debug("Stop RX worker")
        self.started.clear()
        self.rx_worker.join(timeout=10)


    # ───────── Context manager stuff ──────── #
    
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()


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
        rq = PRPC_Request(self, abort_callback=lambda rq: self._id_free())
        with self.req_lock:
            if self.reqs[frame.seq_id] is not None:
                raise ValueError("Frame seq. id {frame.seq_id} is already waiting for a response")

            else:
                frame_enc = frame.encode()
                self.log.debug(f"Transmit frame: {frame_enc}")

                # Send frame
                self.io.write(frame_enc.encode(self.encoding))
                self.io.flush()

                # Enqueue frame
                self.reqs[frame.seq_id] = rq
                return rq


    # ─────────────── RX worker ────────────── #

    def _dispatch(self, frame):
        # Frame is a response
        if frame.is_response():
            with self.req_lock:
                if frame.seq_id is None:
                    self.log.warning(f"Received notification with a response identifier: {frame}. These are invalid and ignored.")

                elif frame.seq_id >= len(self.reqs):
                    self.log.error(f"Received a response frame ({frame}) with a sequence ID above limit ({self.max_reqs}). It will be ignored." )

                elif self.reqs[frame.seq_id] is not None:
                    req = self.reqs[frame.seq_id]
                    self.reqs[frame.seq_id] = None # Slot is free!
                    req.result.put(frame)
                    self._id_free(frame.seq_id)

                else:
                    self.log.warning(f"Received a response ({frame}) for an uknown sequence ID. It will be ignored.")

        # Frame is a request
        else:
            self.log.warning("Requests are not handled for now.")
            pass # TODO # Handle requests

    def _process_line(self, line):
        self.log.debug(f"Received line: {line!r}")
        try:
            frame = prpc.parse(line)
            self.log.debug(f"Decoded PRPC Frame: {frame}")
            self._dispatch(frame)

        except prpc.ParseError as exc:
            self.log.error(f"Failed to parse message: {exc}")
            self.log.debug(traceback.format_exc())
    
    def _rx_worker(self):
        line_buffer = ""

        self.log.debug("Started RX worker")
        while self.started.is_set():
            # Read a character and append it to input string buffer
            rbuf = self.io.read(1)
            try:
                line_buffer += rbuf.decode(self.encoding)
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

        self.log.debug("Stopped RX worker")
