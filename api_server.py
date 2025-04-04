# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-web-server-micropython/

# Import necessary modules
import network
import socket
import time
import random
import json
from machine import Pin, RTC
import qwiic_bme280
import uerrno # For non-blocking socket errors

# --- Configuration ---
# Wi-Fi credentials are imported later from secrets
# Sensor History Configuration
SAVE_INTERVAL_S = 60  # Save data every 60 seconds
HISTORY_DURATION_S = 86400 # Keep data for 24 hours (in seconds)

# --- Global Variables ---
historical_data = [] # List to store sensor readings as tuples: (timestamp, temp_f, pressure_pa, humidity_pct, altitude_ft)
last_save_ticks_ms = time.ticks_ms() # Use ticks_ms for interval timing

print("\nApi Server for PiMoroni Pico Plus 2w with SparkFun BME280\n")
mySensor = qwiic_bme280.QwiicBme280()

if mySensor.connected == False:
    print("The Qwiic BME280 device isn't connected to the system. Please check your connection", \
        file=sys.stderr)
    exit()

#print("SparkFun BME280 Sensor Init") # Already printed essentially
try:
    mySensor.begin()
    print("BME280 Initialized.")
except Exception as e:
    print(f"Error initializing BME280: {e}")

# Setup the LED pin.
led = Pin('LEDW', Pin.OUT)

# Wi-Fi credentials
from secrets import WIFI_SSID, WIFI_PASSWORD
ssid = WIFI_SSID
password = WIFI_PASSWORD

# --- Helper Functions ---

def _get_current_sensor_tuple():
    """Reads sensor and returns data as a tuple."""
    if mySensor.connected:
        try:
            # Trigger readings - properties might cache otherwise
            t = mySensor.temperature_fahrenheit
            p = mySensor.pressure
            h = mySensor.humidity
            a = mySensor.altitude_feet
            # Return the tuple
            return (t, p, h, a)
        except Exception as e:
            print(f"Error reading sensor: {e}")
            return (None, None, None, None)
    else:
        # Return None or default values if sensor disconnects
        return (None, None, None, None)

# HTML template for the webpage
def webpage(current_sensor_tuple, led_state):
    """Generates the HTML webpage content."""
    temp, press, hum, alt = current_sensor_tuple
    temp_str = f"{temp:.2f}" if temp is not None else "N/A"
    press_str = f"{press:.2f}" if press is not None else "N/A" # Assuming Pa needs .2f is okay, adjust if needed
    hum_str = f"{hum:.2f}" if hum is not None else "N/A"
    alt_str = f"{alt:.2f}" if alt is not None else "N/A"
    html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Pico Web Server</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #333; }}
                .sensor-data p {{ margin: 5px 0; }}
                .controls form {{ display: inline-block; margin-right: 10px; }}
                input[type="submit"] {{ padding: 10px 15px; cursor: pointer; }}
            </style>
        </head>
        <body>
            <h1>Raspberry Pi Pico W Sensor Server</h1>
            <h2>Led Control</h2>
            <div class="controls">
                <form action="./lighton">
                    <input type="submit" value="Light ON" />
                </form>
                <form action="./lightoff">
                    <input type="submit" value="Light OFF" />
                </form>
                <p>LED state: <strong>{led_state}</strong></p>
            </div>
            <h2>Current Sensor Readings</h2>
            <div class="sensor-data">
                <p>Temperature: {temp_str} °F</p>
                <p>Barometric Pressure: {press_str} Pa</p>
                <p>Humidity: {hum_str} %</p>
                <p>Approx. Altitude: {alt_str} ft</p>
            </div>
            <p><small>Page refreshes automatically every 30 seconds.</small></p>
            <p><small>To get all historical data (last 24h): <a href="/sensor?all=true">/sensor?all=true</a></small></p>
        </body>
        </html>
        """
    return str(html)

# Connect to WLAN and setup RTC
rtc = RTC()

# Connect to WLAN
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for Wi-Fi connection
connection_timeout = 15
while connection_timeout > 0:
    if wlan.status() >= 3:
        break
    connection_timeout -= 1
    print('.', end='')
    time.sleep(1)

print() # Newline after dots

# Check if connection is successful
if wlan.status() != 3:
    raise RuntimeError('Failed to establish a network connection')
else:
    print('Connection successful!')
    network_info = wlan.ifconfig()
    print('IP address: http://' + network_info[0])
    ip_address = network_info[0] # Store IP address
    # Attempt to sync RTC with NTP - requires internet access
    # Note: ntptime might not be built-in on all Pico W MicroPython builds
    try:
        import ntptime
        print("Attempting to sync RTC with NTP...")
        ntptime.settime()
        print(f"RTC synced: {rtc.datetime()}")
    except ImportError:
        print("NTP module not available. RTC not synced.")
    except OSError as e:
        print(f"Could not sync RTC with NTP: {e}")

def log_historical_data():
    """Checks interval, logs sensor data, and prunes old data."""
    global last_save_ticks_ms, historical_data
    now_ticks = time.ticks_ms()
    # Check if SAVE_INTERVAL_S has passed
    if time.ticks_diff(now_ticks, last_save_ticks_ms) >= SAVE_INTERVAL_S * 1000:
        current_data_tuple = _get_current_sensor_tuple()
        # Only save if sensor reading was successful
        if all(val is not None for val in current_data_tuple):
            current_timestamp = time.time() # Get absolute time (requires RTC sync)
            historical_data.append((current_timestamp,) + current_data_tuple)
            last_save_ticks_ms = now_ticks # Reset interval timer
            print(f"Logged data at {current_timestamp}. Total points: {len(historical_data)}")

            # Prune old data (more efficient to check the oldest first)
            now = time.time()
            while historical_data and (now - historical_data[0][0] > HISTORY_DURATION_S):
                removed = historical_data.pop(0)
                # print(f"Removed old data point: {removed[0]}") # Can be verbose
        else:
             print("Skipping logging: Sensor read failed.")

# Set up socket and start listening
addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(addr)
s.listen(5) # Increase backlog

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

print("\n--- API Endpoints ---")
print(f"  http://{ip_address}/sensor     - Get current sensor data (JSON)")
print(f"  http://{ip_address}/sensor?all=true - Get historical data (last 24h, JSON)")
print("\nServer started. Waiting for connections...")

# Main loop to listen for connections
while True:
    # --- Periodic Tasks (run every loop iteration) ---
    try:
        log_historical_data()
    except Exception as e:
        print(f"Error during periodic tasks: {e}")

    # --- Handle Web Requests ---
    conn = None # Ensure conn is defined
    try:
        # Accept connection (blocking call)
        conn, addr = s.accept()
        conn.settimeout(5.0) # Set timeout for recv
        print(f'\nReceived connection from {addr}')

        # Receive and parse the request
        request_bytes = conn.recv(1024)
        conn.settimeout(None) # Disable timeout after recv
        request_str = request_bytes.decode('utf-8')
        # print('Request content = %s' % request_str) # Can be verbose

        # Simple request parsing
        request_line = request_str.split('\r\n')[0]
        parts = request_line.split()
        response = ""
        content_type = 'text/html' # Default
        status_code = 200 # Default

        if len(parts) >= 2:
            method = parts[0]
            path = parts[1]
            print(f"Request: {method} {path}")

            # Process the request and update variables
            if path == '/lighton' or path == '/lighton?':
                print("LED on")
                led.value(1)
                state = "ON"
                # Generate HTML response
                response = webpage(_get_current_sensor_tuple(), state)
            elif path == '/lightoff' or path == '/lightoff?':
                led.value(0)
                state = 'OFF'
                print("LED off")
                # Generate HTML response
                response = webpage(_get_current_sensor_tuple(), state)
            # --- New Endpoint Logic ---
            elif path == '/sensor?all=true':
                 print(f"Historical data requested. Sending {len(historical_data)} points.")
                 # Directly dump the list of tuples: [(ts, temp, prs, hum, alt), ...]
                 response = json.dumps(historical_data)
                 content_type = 'application/json'
            elif path == '/sensor' or path == '/sensor?':
                print("Current sensor data requested.")
                current_data = _get_current_sensor_tuple()
                if all(v is not None for v in current_data):
                    # Structure as a dictionary for clarity
                    data_dict = {
                        "timestamp": time.time(), # Add current timestamp
                        "temperature_f": current_data[0],
                        "pressure_pa": current_data[1],
                        "humidity_percent": current_data[2],
                        "altitude_ft": current_data[3]
                    }
                    response = json.dumps(data_dict)
                    content_type = 'application/json'
                else:
                    status_code = 503 # Service Unavailable (sensor failed)
                    response = json.dumps({"error": "Sensor read failure"})
                    content_type = 'application/json'
            # --- End New Endpoint Logic ---
            # Keep the root path handler
            elif path == '/' or path == '/?':
                 response = webpage(_get_current_sensor_tuple(), state)
            # Handle unknown paths
            else:
                 status_code = 404
                 response = "Not Found"
                 content_type = 'text/plain'

        else: # Malformed request
            status_code = 400
            response = "Bad Request"
            content_type = 'text/plain'

        # Send the HTTP response and close the connection
        conn.send(f'HTTP/1.0 {status_code} OK\r\n') # Use status_code
        conn.send(f'Content-type: {content_type}\r\n')
        conn.send('Connection: close\r\n\r\n') # Close connection after response
        # Ensure response is encoded
        if isinstance(response, str):
             conn.sendall(response.encode('utf-8'))
        else:
             # Should already be JSON string, but double-check encoding
             conn.sendall(str(response).encode('utf-8'))

    except OSError as e:
        # Handle specific OS errors like timeout or connection reset
        if e.errno == uerrno.ETIMEDOUT:
            print("Connection timed out.")
        elif e.errno == uerrno.ECONNRESET:
            print("Connection reset by peer.")
        else:
            print(f'OSError handling connection: {e}')
    except Exception as e:
        # Catch other potential errors during request handling
        print(f'Error processing request: {e}')
        # Try to send an error response if connection is still open
        if conn and status_code == 200: # Only if no other error code was set
            try:
                conn.send('HTTP/1.0 500 Internal Server Error\r\n')
                conn.send('Content-type: text/plain\r\n')
                conn.send('Connection: close\r\n\r\n')
                conn.send('Internal Server Error')
            except Exception as send_err:
                print(f"Could not send error response: {send_err}")
    finally:
        # Ensure connection is closed
        if conn:
            conn.close()
            # print("Connection closed.") # Can be verbose

    # Small delay to prevent high CPU usage if accept returns immediately
    # and log_historical_data doesn't take much time.
    # time.sleep_ms(10)