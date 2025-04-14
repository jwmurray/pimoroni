#-----------------------------------------------------------------------------
# qwiic_oled_display.py
#
#------------------------------------------------------------------------
#
# Written by  SparkFun Electronics, May 2019
# Modified for MicroPython on Raspberry Pi Pico W
#
# More information on qwiic is at https:= www.sparkfun.com/qwiic
#
# Do you like this library? Help support SparkFun. Buy a board!
#
#==================================================================================
# Copyright (c) 2019 SparkFun Electronics
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
#
# This is mostly a port of existing Arduino functionaly, so pylint is sad.
# The goal is to keep the public interface pthonic, but internal is internal
#
# pylint: disable=line-too-long, bad-whitespace, invalid-name, too-many-lines
# pylint: disable=too-many-lines, too-many-arguments, too-many-instance-attributes
# pylint: disable=too-many-public-methods

"""
qwiic_oled_display
======================
Python module for the [Qwiic OLED Display](https://www.sparkfun.com/products/17153)

This python package is a port of the existing [SparkFun Micro OLED Arduino Library](https://github.com/sparkfun/SparkFun_Micro_OLED_Arduino_Library)

This package can be used in conjunction with the overall [SparkFun qwiic Python Package](https://github.com/sparkfun/Qwiic_Py)

New to qwiic? Take a look at the entire [SparkFun qwiic ecosystem](https://www.sparkfun.com/qwiic).

"""

import math
from machine import I2C

# Define the device name and I2C addresses
_DEFAULT_NAME = "Qwiic OLED Display (128x32)"
_AVAILABLE_I2C_ADDRESS = [0x3C, 0x3D]
_LCDWIDTH = 128
_LCDHEIGHT = 32
_PAGES = 4  # 32 pixels height / 8 pixels per page = 4 pages

# SSD1306 Commands
_SSD1306_SETCONTRAST = 0x81
_SSD1306_DISPLAYALLON_RESUME = 0xA4
_SSD1306_DISPLAYALLON = 0xA5
_SSD1306_NORMALDISPLAY = 0xA6
_SSD1306_INVERTDISPLAY = 0xA7
_SSD1306_DISPLAYOFF = 0xAE
_SSD1306_DISPLAYON = 0xAF
_SSD1306_SETDISPLAYOFFSET = 0xD3
_SSD1306_SETCOMPINS = 0xDA
_SSD1306_SETVCOMDETECT = 0xDB
_SSD1306_SETDISPLAYCLOCKDIV = 0xD5
_SSD1306_SETPRECHARGE = 0xD9
_SSD1306_SETMULTIPLEX = 0xA8
_SSD1306_SETLOWCOLUMN = 0x00
_SSD1306_SETHIGHCOLUMN = 0x10
_SSD1306_SETSTARTLINE = 0x40
_SSD1306_MEMORYMODE = 0x20
_SSD1306_COLUMNADDR = 0x21
_SSD1306_PAGEADDR = 0x22
_SSD1306_COMSCANINC = 0xC0
_SSD1306_COMSCANDEC = 0xC8
_SSD1306_SEGREMAP = 0xA0
_SSD1306_CHARGEPUMP = 0x8D
_SSD1306_EXTERNALVCC = 0x1
_SSD1306_SWITCHCAPVCC = 0x2

# Basic 5x8 font (only includes characters we need for "Hello World")
_FONT = {
    'H': [0x7F, 0x08, 0x08, 0x08, 0x7F],
    'e': [0x38, 0x54, 0x54, 0x54, 0x18],
    'l': [0x00, 0x41, 0x7F, 0x40, 0x00],
    'o': [0x38, 0x44, 0x44, 0x44, 0x38],
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00],
    'W': [0x7F, 0x20, 0x18, 0x20, 0x7F],
    'r': [0x38, 0x04, 0x04, 0x04, 0x08],
    'd': [0x30, 0x48, 0x48, 0x48, 0x7F]
}

class QwiicOledDisplay:
    """
    QwiicOledDisplay - MicroPython version
    
    :param i2c: The I2C bus to use
    :param address: The I2C address to use for the device (default: 0x3C)
    """
    
    def __init__(self, i2c, address=0x3C):
        self.i2c = i2c
        self.address = address
        self.width = _LCDWIDTH
        self.height = _LCDHEIGHT
        self.pages = _PAGES
        # Buffer size is width * pages (each page is 8 pixels tall)
        self.buffer = bytearray(self.width * self.pages)
        
    def _command(self, cmd):
        """Send a command to the display"""
        self.i2c.writeto(self.address, b'\x00' + bytes([cmd]))
        
    def begin(self):
        """Initialize the OLED display"""
        try:
            # Turn display off
            self._command(_SSD1306_DISPLAYOFF)
            
            # Set display clock
            self._command(_SSD1306_SETDISPLAYCLOCKDIV)
            self._command(0x80)
            
            # Set multiplex ratio
            self._command(_SSD1306_SETMULTIPLEX)
            self._command(0x1F)  # 32 rows
            
            # Set display offset
            self._command(_SSD1306_SETDISPLAYOFFSET)
            self._command(0x00)
            
            # Set start line
            self._command(_SSD1306_SETSTARTLINE | 0x00)
            
            # Charge pump
            self._command(_SSD1306_CHARGEPUMP)
            self._command(0x14)  # Enable charge pump
            
            # Memory mode
            self._command(_SSD1306_MEMORYMODE)
            self._command(0x00)  # Horizontal addressing mode
            
            # Segment remap
            self._command(_SSD1306_SEGREMAP | 0x01)
            
            # COM scan direction
            self._command(_SSD1306_COMSCANDEC)
            
            # Set COM pins
            self._command(_SSD1306_SETCOMPINS)
            self._command(0x02)  # Sequential COM pin configuration
            
            # Set contrast
            self._command(_SSD1306_SETCONTRAST)
            self._command(0x8F)
            
            # Set precharge
            self._command(_SSD1306_SETPRECHARGE)
            self._command(0xF1)
            
            # Set VCOM detect
            self._command(_SSD1306_SETVCOMDETECT)
            self._command(0x40)
            
            # Display all on resume
            self._command(_SSD1306_DISPLAYALLON_RESUME)
            
            # Normal display
            self._command(_SSD1306_NORMALDISPLAY)
            
            # Turn display on
            self._command(_SSD1306_DISPLAYON)
            
            return True
        except OSError:
            return False
            
    def clear(self):
        """Clear the display buffer"""
        self.buffer = bytearray(self.width * self.pages)
        
    def display(self):
        """Update the display with the contents of the buffer"""
        # Set column address range
        self._command(_SSD1306_COLUMNADDR)
        self._command(0)  # Column start address
        self._command(self.width - 1)  # Column end address
        
        # Set page address range
        self._command(_SSD1306_PAGEADDR)
        self._command(0)  # Page start address
        self._command(self.pages - 1)  # Page end address
        
        # Write the buffer
        for i in range(0, len(self.buffer), 16):
            self.i2c.writeto(self.address, b'\x40' + self.buffer[i:i+16])
            
    def print(self, text, x=0, y=0):
        """Print text to the display buffer"""
        # Convert y position to page number (each page is 8 pixels tall)
        page = y // 8
        if page >= self.pages:
            return  # Don't print if page is out of range
            
        # Simple text printing implementation
        for i, char in enumerate(text):
            if x + i * 6 < self.width:  # 5 pixels per char + 1 pixel spacing
                self._draw_char(x + i * 6, page, char)
                
    def _draw_char(self, x, page, char):
        """Draw a single character at the specified position"""
        if char in _FONT:
            # Get the font data for this character
            font_data = _FONT[char]
            # Draw each column of the character
            for col in range(5):  # 5 columns per character
                if x + col < self.width:
                    # Write the column data to the buffer
                    self.buffer[page * self.width + x + col] = font_data[col]