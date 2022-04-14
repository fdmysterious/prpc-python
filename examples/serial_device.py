"""
┌────────────────────────────────────────────────────────┐
│ Simple example on how to use a serial device with PRPC │
└────────────────────────────────────────────────────────┘

 Florian Dupeyron
 April 2022
"""

import serial
import io

import time

from   prpc.handler import PRPC_IOHandler
from   prpc         import PRPC_Frame

SERIAL_PATH="/dev/ttyACM0"

if __name__ == "__main__":
    # Create serial device and associated io object
    sdev               = serial.serial_for_url(SERIAL_PATH, do_not_open=True)

    sdev.baudrate      = 115200
    sdev.bytesize      = serial.EIGHTBITS
    sdev.parity        = serial.PARITY_NONE
    sdev.stopbits      = serial.STOPBITS_ONE
    sdev.rtscts        = 0

    sdev.timeout       = 1
    sdev.write_timeout = 5


    # Create handler
    prpc_handler       = PRPC_IOHandler(sdev)

    # Open stuff
    try:
        sdev.open()
        prpc_handler.start()

        while True:
            print("Doing hello request!")
            rq     = prpc_handler.req("hello")
            result = rq.wait()
            print("Result: ", result)

            time.sleep(1)

    finally:
        sdev.cancel_read()
        prpc_handler.stop()
        sdev.close()
