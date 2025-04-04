#! /usr/bin/env python3

import asyncio
import struct
import time
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator, FuncFormatter, MultipleLocator
from datetime import datetime, timedelta
from collections import deque
import argparse
import math
import bleak
from bleak import BleakClient, BleakScanner

# --- Configuration ---
# **IMPORTANT**: Use the same UUIDs you generated and put in the Pico's main.py
SERVICE_UUID = "db6dde59-92af-4935-8309-e51ddc0a9651"
CHARACTERISTIC_UUID = "db6dde59-92af-4935-8309-e51ddc0a9652"
DEVICE_NAME = "PicoSensor"  # The name the Pico advertises

# --- Formatting functions for Y-axis ticks ---
def format_temp_humid(value, pos):
    return f'{value:.1f}'
def format_pressure(value, pos):
    return f'{int(value)}'
def format_altitude(value, pos):
    return f'{int(value)}'

# --- Formatting function for X-axis time ticks ---
def format_xaxis_time(value, pos):
    try:
        dt_object = mdates.num2date(value)
        return dt_object.strftime('%H:%M:%S') # Simplified format for clarity
    except ValueError:
        return ""

class SensorMonitorBLE:
    def __init__(self, update_interval=5,
                 time_window_minutes=1440, initial_time_window_minutes=6):
        self.update_interval = update_interval # Target interval (BLE notification drives actual)
        self.max_time_window_minutes = time_window_minutes
        self.max_time_window_seconds = time_window_minutes * 60
        self.start_time = None
        self.last_data_time = None

        # Calculate max_points needed - Note: This is less critical if relying only on notifications
        # but good for plotting history if connection drops temporarily.
        # We estimate points based on the *intended* interval.
        self.max_points = math.ceil((self.max_time_window_seconds / self.update_interval) * 1.1)
        print(f"Aiming to store approx: {self.max_points} points")

        # Initialize data storage
        self.timestamps = deque(maxlen=self.max_points)
        self.temperature_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)
        self.humidity_data = deque(maxlen=self.max_points)
        self.altitude_data = deque(maxlen=self.max_points)

        # BLE connection state
        self.client: BleakClient | None = None
        self.connected = False
        self.notification_queue = asyncio.Queue() # Queue to pass data from BLE callback

        # Setup plot
        self.setup_plot()

    def setup_plot(self):
        # ... (Plot setup is largely the same as monitor.py's subplots version) ...
        plt.rcParams['axes.formatter.useoffset'] = False
        self.fig, axs = plt.subplots(4, 1, sharex=True, figsize=(12, 10))
        self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt = axs

        for ax in axs:
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.grid(True, linestyle='--', alpha=0.7)

        self.temp_line, = self.ax_temp.plot([], [], color='red')
        self.press_line, = self.ax_press.plot([], [], color='blue')
        self.humid_line, = self.ax_humid.plot([], [], color='green')
        self.alt_line, = self.ax_alt.plot([], [], color='purple')

        self.ax_temp.set_title('Temperature')
        self.ax_temp.set_ylabel('Temp (°F)')
        self.ax_press.set_title('Barometric Pressure')
        self.ax_press.set_ylabel('Pressure (Pa)')
        self.ax_humid.set_title('Humidity')
        self.ax_humid.set_ylabel('Humidity (%)')
        self.ax_alt.set_title('Altitude')
        self.ax_alt.set_ylabel('Altitude (ft)')
        self.ax_alt.set_xlabel('Time')

        locator = mdates.AutoDateLocator(minticks=3, maxticks=10)
        formatter = FuncFormatter(format_xaxis_time) # Use simplified HH:MM:SS for now
        self.ax_alt.xaxis.set_major_locator(locator)
        self.ax_alt.xaxis.set_major_formatter(formatter)

        self.fig.suptitle('Real-time Sensor Data via BLE', fontsize=16, y=0.98)
        plt.tight_layout()
        self.fig.subplots_adjust(top=0.92, hspace=0.4)

    def update_data_ranges(self):
        # ... (This function remains identical to the monitor.py version using subplots) ...
        axes = [self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt]
        formatters = [format_temp_humid, format_pressure, format_temp_humid, format_altitude]
        data_sets = [self.temperature_data, self.pressure_data, self.humidity_data, self.altitude_data]
        keys = ['temperature', 'pressure', 'humidity', 'altitude']

        for i, (ax, data, key, formatter) in enumerate(zip(axes, data_sets, keys, formatters)):
            if data:
                current_min = min(data)
                current_max = max(data)
                data_range = current_max - current_min

                if data_range < 1e-6:
                    if key == 'temperature' or key == 'humidity': buffer = 0.5
                    elif key == 'pressure': buffer = 50
                    else: buffer = 5
                    min_val = current_min - buffer
                    max_val = current_max + buffer
                else:
                    buffer = data_range * 0.10
                    min_val = current_min - buffer
                    max_val = current_max + buffer

                ax.set_ylim(min_val, max_val)
                tick_range = max_val - min_val
                num_ticks_target = 5

                # Determine major step
                if key == 'temperature':
                    if tick_range <= 1: major_step = 0.2
                    elif tick_range <= 2: major_step = 0.5
                    elif tick_range <= 5: major_step = 1.0
                    elif tick_range <= 10: major_step = 2.0
                    else: major_step = max(1.0, round(tick_range / num_ticks_target))
                    minor_step = major_step / 5.0
                elif key == 'pressure':
                    major_step = max(100, np.ceil(tick_range / num_ticks_target / 100) * 100)
                    minor_step = major_step / 4.0
                elif key == 'humidity':
                    if tick_range <= 2: major_step = 0.5
                    elif tick_range <= 5: major_step = 1.0
                    elif tick_range <= 10: major_step = 2.0
                    else: major_step = max(1.0, round(tick_range / num_ticks_target))
                    minor_step = major_step / 5.0
                else: # altitude
                    major_step = max(10, np.ceil(tick_range / num_ticks_target / 10) * 10)
                    minor_step = major_step / 5.0

                # Use FixedLocator logic to ensure edges are labeled
                start_tick_val = np.ceil(min_val / major_step) * major_step
                end_tick_val = np.floor(max_val / major_step) * major_step
                intermediate_ticks = np.arange(start_tick_val, end_tick_val + major_step * 0.5, major_step)
                tick_locations = sorted(list(set([min_val] + list(intermediate_ticks) + [max_val])))

                final_tick_locations = []
                if tick_locations:
                    final_tick_locations.append(tick_locations[0])
                    min_tick_spacing = major_step * 0.1
                    for i in range(1, len(tick_locations)):
                        if abs(tick_locations[i] - final_tick_locations[-1]) >= min_tick_spacing:
                            final_tick_locations.append(tick_locations[i])
                    if max_val not in final_tick_locations and abs(max_val - final_tick_locations[-1]) >= min_tick_spacing * 0.5:
                         final_tick_locations.append(max_val)

                ax.yaxis.set_major_locator(plt.FixedLocator(final_tick_locations))
                ax.yaxis.set_minor_locator(plt.MultipleLocator(minor_step))
                ax.yaxis.set_major_formatter(FuncFormatter(formatter))


    def format_x_axis(self):
        # ... (This function remains identical to monitor.py version) ...
        if not self.timestamps or not self.start_time:
            return
        end_time = self.timestamps[-1]
        view_start_time = max(
            self.start_time,
            end_time - timedelta(seconds=self.max_time_window_seconds)
        )
        view_end_time = end_time + timedelta(seconds=self.update_interval * 2)
        self.ax_temp.set_xlim(view_start_time, view_end_time)

        start_label = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.ax_alt.set_xlabel(f'Time -- Started at {start_label}')
        # Auto locator/formatter handles the rest
        self.fig.canvas.draw_idle()

    def update_plot(self, frame):
        """Update function called by FuncAnimation."""
        try:
            # Get data from the queue (non-blocking check)
            # If the queue is empty, we just redraw with existing data
            # This decouples BLE notifications from plot updates
            while not self.notification_queue.empty():
                current_time = datetime.now()
                self.last_data_time = current_time

                if not self.start_time:
                    self.start_time = current_time

                try:
                    unpacked_data = self.notification_queue.get_nowait()
                    temp_f, pressure_pa, humidity_pct, altitude_ft = unpacked_data
                except asyncio.QueueEmpty:
                    break # Exit loop if queue is empty

                self.timestamps.append(current_time)
                self.temperature_data.append(temp_f)
                self.pressure_data.append(pressure_pa)
                self.humidity_data.append(humidity_pct)
                self.altitude_data.append(altitude_ft)

            # Only proceed with plot update if we have data
            if not self.timestamps:
                 return self.temp_line, self.press_line, self.humid_line, self.alt_line

            self.update_data_ranges()

            x_data = list(self.timestamps) # Plot datetime objects

            self.temp_line.set_data(x_data, np.array(self.temperature_data))
            self.press_line.set_data(x_data, np.array(self.pressure_data))
            self.humid_line.set_data(x_data, np.array(self.humidity_data))
            self.alt_line.set_data(x_data, np.array(self.altitude_data))

            self.format_x_axis()

            # Update title
            last_reading_time_str = self.last_data_time.strftime("%H:%M:%S") if self.last_data_time else "N/A"
            reading_title = ""
            if self.temperature_data: # Check if lists are populated
                 reading_title = (f'Temp: {self.temperature_data[-1]:.1f}°F, '
                                  f'Press: {self.pressure_data[-1]:.0f}Pa, '
                                  f'Hum: {self.humidity_data[-1]:.1f}%, '
                                  f'Alt: {self.altitude_data[-1]:.0f}ft')

            status = "Connected" if self.connected else "Disconnected"
            self.fig.suptitle(f'BLE Sensor Monitor ({status} - Last: {last_reading_time_str})\n{reading_title}',
                            fontsize=14, y=0.98)

        except Exception as e:
             print(f"Error during plot update: {e}") # Log errors

        return self.temp_line, self.press_line, self.humid_line, self.alt_line

    def notification_handler(self, sender: bleak.backends.characteristic.BleakGATTCharacteristic, data: bytearray):
        """Callback for BLE notifications."""
        #print(f"Received notification: {data.hex()}") # Debug: show raw bytes
        try:
            # Unpack the 16 bytes into four floats (little-endian)
            unpacked_data = struct.unpack("<ffff", data)
            # Put the unpacked data into the queue for the main thread (plot update)
            self.notification_queue.put_nowait(unpacked_data)
        except struct.error as e:
            print(f"Error unpacking data: {e}, received: {data.hex()}")
        except asyncio.QueueFull:
             print("Warning: Notification queue is full, skipping data point.")


    async def run_ble_client(self):
        """Main async function to handle BLE connection and notifications."""
        while True: # Loop to handle reconnections
            self.connected = False
            print(f"Scanning for device: {DEVICE_NAME}...")
            device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=10.0)

            if not device:
                print(f"Device '{DEVICE_NAME}' not found. Retrying in 10s...")
                await asyncio.sleep(10)
                continue

            print(f"Connecting to {device.name} ({device.address})...")

            async with BleakClient(device) as client:
                if client.is_connected:
                    print("Connected!")
                    self.connected = True
                    self.client = client # Store client reference if needed later

                    try:
                        print(f"Starting notifications for characteristic {CHARACTERISTIC_UUID}...")
                        await client.start_notify(CHARACTERISTIC_UUID, self.notification_handler)
                        print("Notifications started. Waiting for data...")

                        # Keep connection alive while matplotlib runs in main thread
                        while client.is_connected:
                             await asyncio.sleep(1.0) # Check connection status periodically

                    except Exception as e:
                        print(f"Error during BLE communication: {e}")
                    finally:
                        print("Stopping notifications...")
                        # Check if still connected before stopping notify
                        if client.is_connected:
                           try:
                               await client.stop_notify(CHARACTERISTIC_UUID)
                           except Exception as e:
                                print(f"Error stopping notifications: {e}")
                        self.connected = False
                        self.client = None
                        print("Disconnected.")

            # If disconnected, wait before retrying
            if not self.connected:
                 print("Waiting 5s before rescanning...")
                 await asyncio.sleep(5)


    def run_animation(self):
         """Runs the Matplotlib animation."""
         # Interval for plot updates (e.g., 100ms for responsiveness)
         # Note: Data arrival is driven by BLE notifications, not this interval.
         ani = animation.FuncAnimation(self.fig, self.update_plot, interval=100, blit=False) # Use the now synchronous update_plot
         plt.show() # This remains the blocking call


async def main_async(args):
    monitor = SensorMonitorBLE(update_interval=args.interval,
                             time_window_minutes=args.time_window)
    # Run BLE client in the background
    ble_task = asyncio.create_task(monitor.run_ble_client())

    # Run matplotlib animation (needs to run in main thread usually)
    # We can't directly await plt.show() as it blocks.
    # Instead, we might need to run the animation loop slightly differently,
    # potentially using fig.canvas.start_event_loop() if available,
    # or just letting the BLE task run and having FuncAnimation update.
    monitor.run_animation() # This will block until the plot window is closed

    # Wait for BLE task to finish if plot is closed (optional cleanup)
    # Note: This might not be reached if plt.show() blocks indefinitely.
    await ble_task


def main():
    parser = argparse.ArgumentParser(description='Monitor Pico sensor data via BLE')
    parser.add_argument('--interval', type=float, default=5.0,
                        help='Target update interval (seconds) - actual rate depends on BLE')
    parser.add_argument('--time-window', type=float, default=1440.0,
                        help='Maximum time window to display in minutes (e.g., 1440 for 24 hours)')
    # Removed --initial-time-window as it's less relevant with this data flow
    # Removed --points as it's calculated

    args = parser.parse_args()

    # Validate arguments (similar to monitor.py)
    if args.interval < 0.1: parser.error("Interval too low")
    if args.time_window < 1 or args.time_window > 2880:
        parser.error("Max time window must be between 1 minute and 2880 minutes (2 days)")

    print(f"Starting BLE sensor monitor...")
    print(f"Target interval: {args.interval}s, Max time window: {args.time_window} minutes")
    print(f"Will connect to '{DEVICE_NAME}' ({SERVICE_UUID} / {CHARACTERISTIC_UUID})")

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("Monitor stopped by user.")

if __name__ == "__main__":
    main()
