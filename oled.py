#!/usr/bin/env python
#-----------------------------------------------------------------------------
# ex2_hello_world.py
#
# "Hello World" Example for the Qwiic OLED Display
#------------------------------------------------------------------------
#
# Written by  SparkFun Electronics, May 2021
# Modified for MicroPython on Raspberry Pi Pico W
#
# This python library supports the SparkFun Electroncis qwiic
# qwiic sensor/board ecosystem on a Raspberry Pi (and compatable) single
# board computers.
#
# More information on qwiic is at https:# www.sparkfun.com/qwiic
#
# Do you like this library? Help support SparkFun. Buy a board!
#
#==================================================================================
# Copyright (c) 2021 SparkFun Electronics
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#==================================================================================
# Example 2 - Simple example to display "hello world" on the Qwiic OLED Display board.
#

import time
from machine import I2C, Pin
import qwiic_oled_display
import sys

def runExample():
    print("\nSparkFun OLED Display - Hello World Example\n")
    
    # Initialize I2C
    i2c = I2C(0, scl=Pin(5), sda=Pin(4))
    
    # Initialize the OLED display
    oled = qwiic_oled_display.QwiicOledDisplay(i2c)
    
    if not oled.begin():
        print("The Qwiic OLED Display isn't connected to the system. Please check your connection")
        return
    
    # Clear the display
    oled.clear()
    
    # Display "Hello World"
    oled.print("Hello World")
    oled.display()
    
    print("Hello World displayed on OLED")

if __name__ == "__main__":
    try:
        runExample()
    except (KeyboardInterrupt, SystemExit) as exErr:
        print("\nEnding Example")
        sys.exit(0)