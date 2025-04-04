import machine
import urequests
from machine import Pin,Timer
import network, time
import utime
import math
import random as rd

####
led = Pin("LED", Pin.OUT)
tim = Timer()
HTTP_HEADERS = {'Content-Type': 'application/json'}
THINGSPEAK_WRITE_API_KEY = 'ZYJZ....R49EDXYZ'  

from secrets import WIFI_SSID, WIFI_PASSWORD
ssid = WIFI_SSID
password = WIFI_PASSWORD


def configure_station(ssid, password):
    # Configure Pico W as Station
    sta_if=network.WLAN(network.STA_IF)
    sta_if.active(True)
    number1 = 0
    for _ in range(10):
            print('connecting to network...')
            sta_if.connect(ssid, password)
            time.sleep(5)
            if sta_if.isconnected():
                print("Connected")
                break
            time.sleep(11)
    return sta_if

sta_if = configure_station(ssid, password)

print('network config:', sta_if.ifconfig())


def tick(timer):
    global led
    led.toggle()

tim.init(freq=1, mode=Timer.PERIODIC, callback=tick)

# Demonstration of generating random data and then sending the data to
# an API on the internet

print("\n\nThis program demonstrates sending data to an API Endpoint on the internet.")
print("An API is an 'Application Programming Interface' that our program talks to on a remote computer.")
print("\nPhones and computers talk on the Internet using many different protocols.")
print("One common protocol is to send data using an HTTP request to an API endpoint on another computer.")
print("\nThis program generates a random integer, e.g. 39.")
print("The program then creates an HTTP POST to an API endpoint on another computer and sends the random integer to the remote computer.")
print("If the send is successful, the program prints 'Successful', meaning that a computer on the internet received the random integer.")
      

while True:
    num = rd.randint(0,100)
    print("\nGenerated random integer to send to the remote computer's API:" ,num)
    time.sleep(1)
    readings = {'field1':num}
    for retries in range(60):     # 60 second reboot timeout
        if sta_if.isconnected():
            print("\tConnecting to remote computer...")
            try:
                computer_name = "api.thingspeak.com"
                url = 'http://' + computer_name + '/update?api_key=' + THINGSPEAK_WRITE_API_KEY
                request = urequests.post(url, json = readings, headers = HTTP_HEADERS )
                
                request.close()
                time.sleep(5)
                print("\tConnected to remove computer", computer_name)
                print("\tWriting encoded integer to ", computer_name, "in JSON string: ", readings)
                print("\tSuccesful!")
                break
            except:
                print("Send failed!")
                time.sleep(1)
        else:
            print(" waiting for wifi to come back.....")
            time.sleep(1)
    else:
        print("Rebooting")
        time.sleep(1)
        machine.reset()  
print("Sent, waiting awhile")
time.sleep(10)