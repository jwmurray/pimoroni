# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-web-server-micropython/

# Import necessary modules
import network
import socket
import time
import random
import json
from machine import Pin
import qwiic_bme280


print("\nApi Server for PiMoroni Pico Plus 2w with SparkFun BME280\n")
mySensor = qwiic_bme280.QwiicBme280()

if mySensor.connected == False:
    print("The Qwiic BME280 device isn't connected to the system. Please check your connection", \
        file=sys.stderr)
    exit()

mySensor.begin()


# Setup the LED pin.
led = Pin('LEDW', Pin.OUT)



# Wi-Fi credentials
from secrets import WIFI_SSID, WIFI_PASSWORD
ssid = WIFI_SSID
password = WIFI_PASSWORD


# HTML template for the webpage
def webpage(random_value, state):
    html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pico Web Server</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body>
            <h1>Raspberry Pi Pico Web Server</h1>
            <h2>Led Control</h2>
            <form action="./lighton">
                <input type="submit" value="Light on" />
            </form>
            <br>
            <form action="./lightoff">
                <input type="submit" value="Light off" />
            </form>
            <p>LED state: {state}</p>
            <h2>Fetch New Value</h2>
            <form action="./value">
                <input type="submit" value="Fetch value" />
            </form>
            <p>Temperature: {mySensor.temperature_fahrenheit}</p>
            <p>Barometric Pressure: {mySensor.pressure}</p>
            <p>Humidity: {mySensor.humidity}</p>
            <p>Altitude: {mySensor.altitude_feet}</p>
        </body>
        </html>
        """
    return str(html)

# Function to get sensor data as JSON
def get_sensor_data():
    sensor_data = {
        "temperature": mySensor.temperature_fahrenheit,
        "barometric_pressure": mySensor.pressure,
        "humidity": mySensor.humidity,
        "altitude": mySensor.altitude_feet
    }
    return json.dumps(sensor_data)

# Individual sensor endpoint functions
def get_temperature():
    temp_data = {"temperature": mySensor.temperature_fahrenheit}
    return json.dumps(temp_data)

def get_pressure():
    pressure_data = {"barometric_pressure": mySensor.pressure}
    return json.dumps(pressure_data)

def get_humidity():
    humidity_data = {"humidity": mySensor.humidity}
    return json.dumps(humidity_data)

def get_altitude():
    altitude_data = {"altitude": mySensor.altitude_feet}
    return json.dumps(altitude_data)

# Connect to WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for Wi-Fi connection
connection_timeout = 10
while connection_timeout > 0:
    if wlan.status() >= 3:
        break
    connection_timeout -= 1
    print('Waiting for Wi-Fi connection...')
    time.sleep(1)

# Check if connection is successful
if wlan.status() != 3:
    raise RuntimeError('Failed to establish a network connection')
else:
    print('Connection successful!')
    network_info = wlan.ifconfig()
    print('IP address: http://' + network_info[0])

# Set up socket and start listening
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen()

print('Listening on', addr)

# Initialize variables
state = "OFF"
random_value = 0

print("\nIn the other programs, the Pico is a client -- meaning it sends data to remote computers.")
print("This time the Pico is the SERVER, waiting for a remote computer to ask the Pico a question.")

print("")
print("The pico is listening to http://" + network_info[0])
print("")
print("  http://" + network_info[0] + "- Show the current web page with buttons to turn the light off and off and a display of all sensors")
print("  http://" + network_info[0] + "/lighton - Turn the pimoroni light on and display the webpage")
print("  http://" + network_info[0] + "/lightoff - Turn the pimoroni light off and display the webpage")

print("")
print("If you are able to connnect to that address, you can get weather data from the Pico server")
print("")
print("API endpoint: http://" + network_info[0] + "/sensor - Returns sensor data as JSON")
print("Individual endpoints:")
print("  http://" + network_info[0] + "/temperature - Returns temperature only in json")
print("  http://" + network_info[0] + "/pressure - Returns barometric pressure only in json")
print("  http://" + network_info[0] + "/humidity - Returns humidity only in json")
print("  http://" + network_info[0] + "/altitude - Returns altitude only in json")


# Main loop to listen for connections
while True:
    try:
        conn, addr = s.accept()
        print('\nReceived a connection from', addr)
        
        # Receive and parse the request
        request = conn.recv(1024)
        request = str(request)
        print('Request content = %s' % request)

        try:
            request = request.split()[1]
            print('Request:', request)
        except IndexError:
            pass
        
        # Process the request and update variables
        if request == '/lighton?' or request == '/lighton':
            print("LED on")
            led.value(1)
            state = "ON"
            # Generate HTML response
            response = webpage(random_value, state)
            content_type = 'text/html'
        elif request == '/lightoff?' or request == '/lightoff':
            led.value(0)
            state = 'OFF'
            # Generate HTML response
            response = webpage(random_value, state)
            content_type = 'text/html'
        elif request == '/value?':
            random_value = random.randint(0, 20)
            # Generate HTML response
            response = webpage(random_value, state)
            content_type = 'text/html'
        elif request == '/sensor' or request == '/sensor?':
            # Generate JSON response for sensor data
            response = get_sensor_data()
            content_type = 'application/json'
            print("Sensor data requested, sending JSON")
        elif request == '/temperature' or request == '/temperature?':
            response = get_temperature()
            content_type = 'application/json'
            print("Temperature requested, sending JSON:", response)
        elif request == '/pressure' or request == '/pressure?':
            response = get_pressure()
            content_type = 'application/json'
            print("Pressure requested, sending JSON:", response)
        elif request == '/humidity' or request == '/humidity?':
            response = get_humidity()
            content_type = 'application/json'
            print("Humidity requested, sending JSON:", response)
        elif request == '/altitude' or request == '/altitude?':
            response = get_altitude()
            content_type = 'application/json'
            print("Altitude requested, sending JSON:", response)
        else:
            # Default: show webpage
            response = webpage(random_value, state)
            content_type = 'text/html'

        # Send the HTTP response and close the connection
        conn.send(f'HTTP/1.0 200 OK\r\nContent-type: {content_type}\r\n\r\n')
        conn.send(response)
        conn.close()

    except OSError as e:
        conn.close()
        print('Connection closed')