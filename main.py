# Complete project details at https://RandomNerdTutorials.com/raspberry-pi-pico-web-server-micropython/

# Import necessary modules
import network
import socket
import time
import random
import json
from machine import Pin, RTC, I2C
import qwiic_bme280
import qwiic_oled_display
import uerrno # For non-blocking socket errors
import sys

# --- Configuration ---
# Wi-Fi credentials are imported later from secrets
# Sensor History Configuration
SAVE_INTERVAL_S = 5  # Save data every 5 seconds
SAVE_TO_FLASH_INTERVAL_S = 900 # Save RAM history to flash every 15 minutes (900 seconds)
HISTORY_DURATION_S = 86400 # Keep data for 24 hours (in seconds)
HISTORY_FILENAME = "sensor_history.json"
# --- Global Variables ---
historical_data = [] # List to store sensor readings as tuples: (timestamp, temp_f, pressure_pa, humidity_pct, altitude_ft)
last_save_ticks_ms = time.ticks_ms() # Use ticks_ms for interval timing
last_flash_save_ticks_ms = time.ticks_ms() # Timer for saving to flash
oled = None # Global OLED display object
mySensor = None

def bme280_init():
    global mySensor
    # Initialize BME280 sensor
    print("\nInitializing BME280 sensor...")
    mySensor = qwiic_bme280.QwiicBme280()
    if not mySensor.connected:
        print("The Qwiic BME280 device isn't connected to the system. Please check your connection", file=sys.stderr)
        sys.exit(1)

    try:
        mySensor.begin()
        print("BME280 Initialized.")
    except Exception as e:
        print(f"Error initializing BME280: {e}", file=sys.stderr)
        sys.exit(1)

def init_oled():
    """Initialize OLED display"""
    global oled
    
    try:
        # Initialize I2C for OLED
        i2c = I2C(0, scl=Pin(5), sda=Pin(4))
        print("I2C initialized")
        
        # Initialize the OLED display
        oled = qwiic_oled_display.QwiicOledDisplay(i2c)
        if not oled.begin():
            print("The Qwiic OLED Display isn't connected to the system. Please check your connection")
            return False
            
        print("OLED display initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing OLED: {e}")
        return False

def oled_display_sensor(data_dict, ip_addr=None):
    """Display sensor data and IP address on the OLED display"""
    global oled
    
    try:
        if oled is None:
            print("OLED display not initialized")
            return
            
        # Use original print statement for dynamic data
        print("Updating OLED display with data:", data_dict, "IP:", ip_addr) # Debug print
        
        # Clear the display first
        oled.clear()
        
        # Format timestamp
        timestamp = time.localtime(data_dict["timestamp"])
        time_str = "{:02d}:{:02d}:{:02d}".format(timestamp[3], timestamp[4], timestamp[5])
        
        # Format temperature and humidity with fixed width
        # Ensure data_dict keys are correct and values are numbers
        temp_str = "{:.1f}F".format(data_dict["temperature_f"])
        hum_str = "{:.1f}%".format(data_dict["humidity_percent"])
        
        print(f"Displaying: Time={time_str}, Temp={temp_str}, Hum={hum_str}, IP={ip_addr}") # Debug print
        
        # Display each line with proper spacing using PIXEL rows
        oled.print("Time: " + time_str, 0, 0)   # Line 1 starts at pixel row 0
        oled.print("Temp: " + temp_str, 0, 8)   # Line 2 starts at pixel row 8
        oled.print("Hum:  " + hum_str, 0, 16)  # Line 3 starts at pixel row 16
        if ip_addr:
            oled.print(ip_addr, 0, 24)       # Line 4 starts at pixel row 24
        
        # Update the display
        oled.display()
        # Use original print statement
        # print("OLED display updated") # Debug print
    except Exception as e:
        print(f"Error updating OLED display: {e}")

def _get_current_sensor_tuple(ip_addr=None):
    """Get current sensor readings as a tuple and update OLED"""
    global mySensor
    
    try:
        # Get current timestamp first
        timestamp = time.time()
        
        # Read sensor data - store in variables to ensure correct order
        temp_f = mySensor.temperature_fahrenheit
        pressure_pa = mySensor.pressure
        humidity_pct = mySensor.humidity
        altitude_ft = mySensor.altitude_feet
        
        # Create data dictionary for OLED display
        data_dict = {
            "timestamp": timestamp,
            "temperature_f": temp_f,
            "humidity_percent": humidity_pct
        }
        
        # Update OLED display, passing the IP address
        oled_display_sensor(data_dict, ip_addr)
        
        # Return tuple in correct order
        return (timestamp, temp_f, pressure_pa, humidity_pct, altitude_ft)
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None

def save_history_to_flash():
    """Saves the current historical_data list (from RAM) to a JSON file on flash."""
    global historical_data
    print(f"Attempting to save history ({len(historical_data)} points) to {HISTORY_FILENAME}...")
    try:
        with open(HISTORY_FILENAME, 'w') as f:
            json.dump(historical_data, f)
        print("History saved successfully.")
        return True
    except OSError as e:
        print(f"Error saving history to flash: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error saving history: {e}")
        return False

def load_history_from_flash():
    """Loads history from the JSON file on flash into the historical_data list (RAM)."""
    global historical_data
    try:
        with open(HISTORY_FILENAME, 'r') as f:
            loaded_data = json.load(f)
            if isinstance(loaded_data, list):
                historical_data = loaded_data
                print(f"Loaded {len(historical_data)} points from {HISTORY_FILENAME}.")
            else:
                print(f"Warning: Data in {HISTORY_FILENAME} is not a list. Starting fresh.")
                historical_data = [] # Ensure it's a list if file is corrupt
    except OSError:
        print(f"{HISTORY_FILENAME} not found. Starting with empty history.")
    except (ValueError, TypeError) as e: # Handle JSON decoding errors
        print(f"Error decoding JSON from {HISTORY_FILENAME}: {e}. Starting fresh.")
        historical_data = [] # Start fresh if file is corrupt

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

def main():
    print("\nApi Server for PiMoroni Pico Plus 2w with SparkFun BME280\n")
    global historical_data, last_save_ticks_ms, last_flash_save_ticks_ms, oled
    ip_address = None # Define ip_address early in main scope

    bme280_init()
    # Initialize OLED
    if not init_oled():
        print("Failed to initialize OLED display.")
    else:
        # Attempt initial sensor read and display update right after OLED init
        # We pass the ip_address here, although it might be None initially
        print("Attempting initial OLED display update...")
        initial_data_tuple = _get_current_sensor_tuple(ip_address) # This calls oled_display_sensor
        if initial_data_tuple is None or not all(v is not None for v in initial_data_tuple):
            print("Initial sensor read failed, OLED might show default state or previous data.")
            # Optional: Display a 'Waiting...' message if the initial read fails
            # try:
            #     if oled:
            #         oled.clear()
            #         oled.print("Waiting...", 0, 8)
            #         oled.display()
            # except Exception as e:
            #     print(f"Error displaying initial waiting message: {e}")

    historical_data = []  # Initialize historical data list
    last_save_ticks_ms = time.ticks_ms()  # Initialize save timestamp
    last_flash_save_ticks_ms = time.ticks_ms()  # Initialize flash save timestamp

    # Setup the LED pin.
    led = Pin('LEDW', Pin.OUT)

    # Wi-Fi credentials
    from secrets import WIFI_SSID, WIFI_PASSWORD
    ssid = WIFI_SSID
    password = WIFI_PASSWORD

    # Connect to WLAN and setup RTC
    rtc = RTC()
    network_info = None  # Initialize network_info to None
    addr = None  # Initialize addr to None
    s = None  # Initialize socket to None

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
        ip_address = network_info[0]  # Store IP address
        print('IP address: http://' + ip_address)
        # Attempt to sync RTC with NTP - requires internet access
        try:
            import ntptime
            print("Attempting to sync RTC with NTP...")
            ntptime.settime()
            print(f"RTC synced: {rtc.datetime()}")
        except ImportError:
            print("NTP module not available. RTC not synced.")
        except OSError as e:
            print(f"Could not sync RTC with NTP: {e}")

        # After connecting and getting IP, update OLED again if possible
        if oled and ip_address:
             print(f"Updating OLED with IP: {ip_address}")
             _get_current_sensor_tuple(ip_address)

    # Load existing history from Flash
    load_history_from_flash()

    # Set up socket and start listening
    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(5) # Increase backlog

        if addr:
            print('Listening on', addr)
        else:
            print('Error: Could not determine listening address')
            return
    except Exception as e:
        print(f'Error setting up socket: {e}')
        return

    # Initialize variables
    state = "OFF"
    random_value = 0

    print("\nIn the other programs, the Pico is a client -- meaning it sends data to remote computers.")
    print("This time the Pico is the SERVER, waiting for a remote computer to ask the Pico a question.")

    print("")
    if ip_address and network_info:
        print("The pico is listening to http://" + ip_address)
        print("")
        print("  http://" + ip_address + "- Show the current web page with buttons to turn the light off and off and a display of all sensors")
        print("  http://" + ip_address + "/lighton - Turn the pimoroni light on and display the webpage")
        print("  http://" + ip_address + "/lightoff - Turn the pimoroni light off and display the webpage")

        print("")
        print(f"History file: {HISTORY_FILENAME} (saved every {SAVE_TO_FLASH_INTERVAL_S}s)")
        print("Warning: Frequent saving wears out flash memory over time.")
        print("If you are able to connnect to that address, you can get weather data from the Pico server")
        print("")
        print("API endpoint: http://" + ip_address + "/sensor - Returns sensor data as JSON")
        print("Individual endpoints:")
        print("  http://" + ip_address + "/temperature - Returns temperature only in json")
        print("  http://" + ip_address + "/pressure - Returns barometric pressure only in json")
        print("  http://" + ip_address + "/humidity - Returns humidity only in json")
        print("  http://" + ip_address + "/altitude - Returns altitude only in json")

        print("\n--- API Endpoints ---")
        print(f"  http://{ip_address}/sensor     - Get current sensor data (JSON)")
        print(f"  http://{ip_address}/sensor?all=true - Get historical data (last 24h, JSON)")
    else:
        print("Warning: No IP address available. Server may not be accessible.")

    print("\nServer started. Waiting for connections...")

    # Main loop to listen for connections
    while True:
        # --- Periodic Tasks (run every loop iteration) ---
        try:
            log_historical_data()
        except Exception as e:
            print(f"Error during periodic tasks: {e}")

        # Check if it's time to save the RAM history to flash
        now_ticks_flash = time.ticks_ms()
        if time.ticks_diff(now_ticks_flash, last_flash_save_ticks_ms) >= SAVE_TO_FLASH_INTERVAL_S * 1000:
            if save_history_to_flash():
                last_flash_save_ticks_ms = now_ticks_flash # Reset flash save timer only on success

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
                    # Generate HTML response, pass IP to update OLED
                    response = webpage(_get_current_sensor_tuple(ip_address), state)
                elif path == '/lightoff' or path == '/lightoff?':
                    led.value(0)
                    state = 'OFF'
                    print("LED off")
                    # Generate HTML response, pass IP to update OLED
                    response = webpage(_get_current_sensor_tuple(ip_address), state)
                # --- New Endpoint Logic ---
                elif path == '/sensor?all=true':
                     print(f"Historical data requested. Sending {len(historical_data)} points.")
                     # Directly dump the list of tuples: [(ts, temp, prs, hum, alt), ...]
                     response = json.dumps(historical_data)
                     content_type = 'application/json'
                elif path == '/sensor' or path == '/sensor?':
                    print("Current sensor data requested.")
                    current_data = _get_current_sensor_tuple(ip_address)
                    if all(v is not None for v in current_data):
                        # Structure as a dictionary for clarity
                        # current_data tuple is (timestamp, temp_f, pressure_pa, humidity_pct, altitude_ft)
                        data_dict = {
                            "timestamp": current_data[0],      # timestamp
                            "temperature_f": current_data[1],  # temp_f
                            "pressure_pa": current_data[2],    # pressure_pa
                            "humidity_percent": current_data[3], # humidity_pct
                            "altitude_ft": current_data[4]     # altitude_ft
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
                     # Pass IP to update OLED
                     response = webpage(_get_current_sensor_tuple(ip_address), state)
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

if __name__ == "__main__":
    main()