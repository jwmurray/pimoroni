import time
from machine import Pin

# Setup the LED pin.
led = Pin('LEDW', Pin.OUT)

# Blink the LED!
while True:

    led.value(1)
    print("On")
    time.sleep(1)

    led.value(0)
    print("Off")
    time.sleep(1)
