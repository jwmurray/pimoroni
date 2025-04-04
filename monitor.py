#! /usr/bin/env python3

import requests
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
import sys

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
        # Convert matplotlib's internal date number to a datetime object
        dt_object = mdates.num2date(value)
        # Format as HH:MM:SS for concise display
        return dt_object.strftime('%H:%M:%S')
    except ValueError:
        # Handle cases where conversion might fail (e.g., during setup)
        return ""

class SensorMonitor:
    def __init__(self, server_url, update_interval=5,
                 time_window_minutes=1440, initial_time_window_minutes=6):
        self.server_url = server_url
        self.sensor_endpoint = f"{server_url}/sensor"
        self.historic_endpoint = f"{self.sensor_endpoint}?all=true" # Endpoint for historic data
        self.update_interval = update_interval # Seconds
        self.max_time_window_minutes = time_window_minutes
        self.max_time_window_seconds = time_window_minutes * 60
        self.initial_time_window_seconds = initial_time_window_minutes * 60

        self.start_time = None # Absolute time of the first data point received
        self.last_fetch_time = 0 # Keep track of fetch times

        # Calculate max_points based on longest duration and interval
        # Add buffer (e.g., 10%) for potential variations
        self.max_points = math.ceil((self.max_time_window_seconds / self.update_interval) * 1.1)
        print(f"Max points to store: {self.max_points}")

        # Use deques for efficient adding/removing from both ends
        self.timestamps = deque(maxlen=self.max_points)
        self.temperature_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)
        self.humidity_data = deque(maxlen=self.max_points)
        self.altitude_data = deque(maxlen=self.max_points)

        # Plot setup
        self.setup_plot()
        self.ani = None # Placeholder for the animation object

    def setup_plot(self):
        # Use a professional and clean plot style
        plt.style.use('seaborn-v0_8-darkgrid')
        plt.rcParams['axes.formatter.useoffset'] = False # Important for pressure/altitude

        # Create subplots (4 rows, 1 column), sharing the x-axis
        self.fig, axs = plt.subplots(4, 1, sharex=True, figsize=(12, 10))
        self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt = axs

        # Apply common settings
        for ax in axs:
            ax.ticklabel_format(useOffset=False, style='plain') # Use plain style, no offsets
            ax.grid(True, linestyle='--', alpha=0.7) # Customize grid

        # Create line objects for each sensor type with distinct colors
        self.temp_line, = self.ax_temp.plot([], [], color='red', marker='.', markersize=3, linestyle='-')
        self.press_line, = self.ax_press.plot([], [], color='blue', marker='.', markersize=3, linestyle='-')
        self.humid_line, = self.ax_humid.plot([], [], color='green', marker='.', markersize=3, linestyle='-')
        self.alt_line, = self.ax_alt.plot([], [], color='purple', marker='.', markersize=3, linestyle='-')

        # Titles and Y-axis labels
        self.ax_temp.set_title('Temperature')
        self.ax_temp.set_ylabel('Temp (°F)')
        self.ax_press.set_title('Barometric Pressure')
        self.ax_press.set_ylabel('Pressure (Pa)')
        self.ax_humid.set_title('Humidity')
        self.ax_humid.set_ylabel('Humidity (%)')
        self.ax_alt.set_title('Altitude')
        self.ax_alt.set_ylabel('Altitude (ft)')

        # X-axis label (initially generic, updated later)
        self.ax_alt.set_xlabel('Time')

        # Configure X-axis major ticks locator and formatter
        locator = mdates.AutoDateLocator(minticks=5, maxticks=12) # Adjust density
        formatter = FuncFormatter(format_xaxis_time) # Use custom HH:MM:SS formatter
        self.ax_alt.xaxis.set_major_locator(locator)
        self.ax_alt.xaxis.set_major_formatter(formatter)

        # Add minor ticks for better granularity
        self.ax_alt.xaxis.set_minor_locator(AutoMinorLocator())
        for ax in axs:
             ax.yaxis.set_minor_locator(AutoMinorLocator())

        # Adjust layout for better spacing and title visibility
        self.fig.suptitle('Real-time Sensor Data', fontsize=16, y=0.98)
        plt.tight_layout()
        self.fig.subplots_adjust(top=0.92, hspace=0.4) # Adjust top for suptitle, hspace between plots

    def fetch_sensor_data(self):
        """Fetches the latest sensor data from the Pico endpoint."""
        try:
            response = requests.get(self.sensor_endpoint, timeout=self.update_interval * 0.8) # Timeout slightly less than interval
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()
            self.last_fetch_time = time.time()
            # Basic validation (check if expected keys exist)
            if all(k in data for k in ['temperature_f', 'pressure_pa', 'humidity_percent', 'altitude_ft']):
                 return data
            else:
                 print(f"Warning: Received incomplete data: {data}")
                 return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from {self.sensor_endpoint}")
            return None

    def update_data_ranges(self):
        """Dynamically adjusts Y-axis limits and ticks based on visible data."""
        axes = [self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt]
        formatters = [format_temp_humid, format_pressure, format_temp_humid, format_altitude]
        # Important: Use the data actually plotted, not the full deque if window is smaller
        # For simplicity now, we use the full deque, assuming it fits within max_time_window
        data_sets = [self.temperature_data, self.pressure_data, self.humidity_data, self.altitude_data]
        keys = ['temperature', 'pressure', 'humidity', 'altitude'] # For logic branching

        for i, (ax, data, key, formatter) in enumerate(zip(axes, data_sets, keys, formatters)):
            if not data: # Skip if no data for this sensor
                continue

            # --- Calculate dynamic Y limits ---
            current_min = min(data)
            current_max = max(data)
            data_range = current_max - current_min

            # Handle near-zero range
            if data_range < 1e-6: # Effectively zero range
                if key == 'temperature' or key == 'humidity': buffer = 0.5
                elif key == 'pressure': buffer = 50 # Larger buffer for pressure
                else: buffer = 5 # Altitude buffer
                min_val = current_min - buffer
                max_val = current_max + buffer
            else:
                # Add 10% buffer on each side
                buffer = data_range * 0.10
                min_val = current_min - buffer
                max_val = current_max + buffer

            # Apply the calculated limits
            ax.set_ylim(min_val, max_val)

            # --- Calculate dynamic Y ticks ---
            tick_range = max_val - min_val
            num_ticks_target = 5 # Aim for roughly this many major ticks

            # Determine major step based on data type and range
            if key == 'temperature':
                if tick_range <= 1: major_step = 0.2
                elif tick_range <= 2: major_step = 0.5
                elif tick_range <= 5: major_step = 1.0
                elif tick_range <= 10: major_step = 2.0
                else: major_step = max(1.0, round(tick_range / num_ticks_target)) # Sensible steps
                minor_step = major_step / 5.0
            elif key == 'pressure':
                # Aim for steps like 100, 200, 500, 1000 Pa
                major_step = max(100, np.ceil(tick_range / num_ticks_target / 100) * 100)
                minor_step = major_step / 4.0
            elif key == 'humidity':
                if tick_range <= 2: major_step = 0.5
                elif tick_range <= 5: major_step = 1.0
                elif tick_range <= 10: major_step = 2.0
                else: major_step = max(1.0, round(tick_range / num_ticks_target))
                minor_step = major_step / 5.0
            else: # altitude
                # Aim for steps like 10, 20, 50, 100 ft
                major_step = max(10, np.ceil(tick_range / num_ticks_target / 10) * 10)
                minor_step = major_step / 5.0

            # Use MultipleLocator for clean, evenly spaced ticks
            ax.yaxis.set_major_locator(plt.MaxNLocator(nbins=num_ticks_target, steps=[1, 2, 2.5, 5, 10])) # Let MaxNLocator choose best steps
            ax.yaxis.set_minor_locator(plt.MultipleLocator(minor_step))
            ax.yaxis.set_major_formatter(FuncFormatter(formatter))

    def format_x_axis(self):
        """Adjusts the X-axis limits based on the time window."""
        if not self.timestamps or not self.start_time:
             return # Nothing to format if no data

        # Determine the end time (most recent timestamp)
        end_time = self.timestamps[-1]

        # Calculate the start time of the view window
        # For live mode, use the sliding window
        view_start_time = max(
            self.start_time, # Don't go earlier than the very first data point
            end_time - timedelta(seconds=self.max_time_window_seconds)
        )

        # Add a small buffer to the end time to prevent the last point being cut off
        view_end_time = end_time + timedelta(seconds=self.update_interval * 2) # Buffer based on update interval

        # Set xlim first so the locator can work with the correct range
        self.ax_temp.set_xlim(view_start_time, view_end_time)

        # AutoDateLocator and our FuncFormatter handle ticks and labels
        # No need for FixedLocator logic here

        # Update the bottom axis label with the session start time
        start_label = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.ax_alt.set_xlabel(f'Time -- Started at {start_label}')

        # Need to trigger redraw if limits or ticks change substantially
        self.fig.canvas.draw_idle()

    def update_plot(self, frame):
        """Update function for animation"""
        # Fetch new data
        data = self.fetch_sensor_data()
        if data:
            current_time = datetime.now()
            # Store the absolute start time on first data point
            if not self.start_time:
                self.start_time = current_time

            self.timestamps.append(current_time)

            # Extract sensor values using new keys
            self.temperature_data.append(data.get('temperature_f', np.nan)) # Use NaN for missing
            self.pressure_data.append(data.get('pressure_pa', np.nan))
            self.humidity_data.append(data.get('humidity_percent', np.nan))
            self.altitude_data.append(data.get('altitude_ft', np.nan))

            # Update the data ranges and y-axis limits/ticks/labels
            self.update_data_ranges()

            # Convert timestamps deque to list for plotting
            x_data = list(self.timestamps)
            if not x_data: # Skip if no data yet
                return self.temp_line, self.press_line, self.humid_line, self.alt_line

            # Update the plot data using datetime objects for x-axis
            self.temp_line.set_data(x_data, np.array(self.temperature_data))
            self.press_line.set_data(x_data, np.array(self.pressure_data))
            self.humid_line.set_data(x_data, np.array(self.humidity_data))
            self.alt_line.set_data(x_data, np.array(self.altitude_data))

            # Format x-axis based on current time range and window
            self.format_x_axis()

            # Update the main title with the last reading time and values
            last_reading_time_str = current_time.strftime("%H:%M:%S")
            # Safely get last values, handle potential NaN
            temp_last = self.temperature_data[-1]
            press_last = self.pressure_data[-1]
            hum_last = self.humidity_data[-1]
            alt_last = self.altitude_data[-1]

            reading_title = (f'Temp: {temp_last:.1f}°F, ' if not np.isnan(temp_last) else 'Temp: N/A, ') + \
                          (f'Pressure: {press_last:.0f}Pa, ' if not np.isnan(press_last) else 'Pressure: N/A, ') + \
                          (f'Humidity: {hum_last:.1f}%, ' if not np.isnan(hum_last) else 'Humidity: N/A, ') + \
                          (f'Altitude: {alt_last:.0f}ft' if not np.isnan(alt_last) else 'Altitude: N/A')

            self.fig.suptitle(f'Real-time Sensor Data (Last Reading: {last_reading_time_str})\n{reading_title}',
                            fontsize=14, y=0.98)

        # Return only the lines
        return self.temp_line, self.press_line, self.humid_line, self.alt_line

    def fetch_and_plot_historic_data(self):
        """Fetches all historic data, plots it, and returns True on success."""
        """Fetches all historic data and plots it statically."""
        print(f"Fetching historic data from {self.historic_endpoint}...")
        try:
            response = requests.get(self.historic_endpoint, timeout=20) # Longer timeout for potentially large data
            response.raise_for_status()
            historic_raw = response.json()

            if not isinstance(historic_raw, list):
                print(f"Error: Expected a list from historic endpoint, got {type(historic_raw)}")
                return False # Indicate failure

            print(f"Received {len(historic_raw)} historic data points.")
            if not historic_raw:
                print("No historic data received.")
                return False # Indicate nothing loaded

            # Clear any existing live data
            self.timestamps.clear()
            self.temperature_data.clear()
            self.pressure_data.clear()
            self.humidity_data.clear()
            self.altitude_data.clear()

            # Process historic data (list of [timestamp, temp, press, hum, alt])
            # Assume timestamp is Unix epoch float/int
            for entry in historic_raw:
                if len(entry) == 5:
                    try:
                        ts, temp, press, hum, alt = entry
                        dt_object = datetime.fromtimestamp(ts)
                        self.timestamps.append(dt_object)
                        self.temperature_data.append(temp if temp is not None else np.nan)
                        self.pressure_data.append(press if press is not None else np.nan)
                        self.humidity_data.append(hum if hum is not None else np.nan)
                        self.altitude_data.append(alt if alt is not None else np.nan)
                    except (TypeError, ValueError) as e:
                        print(f"Warning: Skipping invalid historic entry {entry}: {e}")
                else:
                    print(f"Warning: Skipping malformed historic entry: {entry}")

            if not self.timestamps:
                 print("No valid historic data processed.")
                 return False # Indicate failure

            # Set start time for labeling
            self.start_time = self.timestamps[0]

            # Update plot data
            x_data = list(self.timestamps)
            self.temp_line.set_data(x_data, np.array(self.temperature_data))
            self.press_line.set_data(x_data, np.array(self.pressure_data))
            self.humid_line.set_data(x_data, np.array(self.humidity_data))
            self.alt_line.set_data(x_data, np.array(self.altitude_data))

            # Update axes ranges based on the full historic data
            self.update_data_ranges()

            # Set X limits to show the entire historic range
            view_start_time = self.timestamps[0] - timedelta(minutes=1) # Small buffer
            view_end_time = self.timestamps[-1] + timedelta(minutes=1) # Small buffer
            self.ax_temp.set_xlim(view_start_time, view_end_time)

            # Update labels and title for historic view
            start_label = self.start_time.strftime("%Y-%m-%d %H:%M")
            end_label = self.timestamps[-1].strftime("%Y-%m-%d %H:%M")
            self.ax_alt.set_xlabel(f'Time (Historic Data from {start_label} to {end_label})')
            self.fig.suptitle(f'Historic Sensor Data ({len(self.timestamps)} points)', fontsize=16, y=0.98)

            # Ensure plot redraws
            self.fig.canvas.draw_idle()
            return True # Indicate success

        except requests.exceptions.RequestException as e:
            print(f"Error fetching historic data: {e}")
            return False
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON response from {self.historic_endpoint}")
            return False
        except Exception as e:
             print(f"An unexpected error occurred during historic data processing: {e}")
             return False

    def run_live(self):
        """Run the animation for live data monitoring (or continuation)."""
        # Keep blit=False for robustness with subplots
        self.ani = animation.FuncAnimation(
            self.fig, self.update_plot, interval=self.update_interval*1000, blit=False)
        plt.show()

def main():
    parser = argparse.ArgumentParser(description='Monitor Pico sensor data in real-time or view historic data')
    parser.add_argument('--server', type=str, default='http://192.168.0.201', # Default IP, CHANGE IF NEEDED
                        help='URL of the Pico API server (e.g., http://192.168.1.123)')
    parser.add_argument('--interval', type=float, default=5.0,
                        help='Update interval in seconds for live monitoring (1-3600)')
    parser.add_argument('--time-window', type=float, default=1440.0,
                        help='Maximum time window to display in minutes for live monitoring (e.g., 1440 for 24 hours)')
    # --- Historic Flag ---
    parser.add_argument('--historic', action='store_true',
                        help='Fetch and display all available historic data instead of live monitoring.')
    parser.add_argument('--continue', dest='continue_live', action='store_true',
                        help='After displaying historic data, continue with live monitoring (requires --historic).')

    args = parser.parse_args()

    # --- Argument Validation ---
    if not args.historic: # Only validate live-mode args if not historic
        if args.interval < 1 or args.interval > 3600:
            parser.error("Interval must be between 1 second and 3600 seconds (1 hour)")
        if args.time_window < 1 or args.time_window > 2880: # Allow up to 2 days
            parser.error("Max time window must be between 1 minute and 2880 minutes (2 days)")

    if args.continue_live and not args.historic:
        parser.error("--continue flag requires --historic flag to be set.")

    # --- Instantiate Monitor ---
    # Note: initial_time_window removed for simplicity, starts with max window now
    monitor = SensorMonitor(args.server, args.interval, args.time_window)

    # --- Mode Selection ---
    if args.historic:
        print(f"Historic mode activated - fetching from {args.server}")
        historic_loaded = monitor.fetch_and_plot_historic_data()

        if args.continue_live:
            if historic_loaded:
                print("Historic data loaded. Continuing with live monitoring...")
                monitor.run_live() # Start live updates after historic plot
            else:
                print("Failed to load historic data. Cannot continue live monitoring.")
        else: # Just historic, no continue
            print("Displaying static historic plot. Close window to exit.")
            plt.show() # Show the static plot now
            print("Historic data plot closed.")
    else:
        print(f"Starting live sensor monitor - connecting to {args.server}")
        print(f"Update interval: {args.interval}s")
        print(f"Max time window: {args.time_window} minutes")
        try:
            monitor.run_live()
        except KeyboardInterrupt:
             print("\nLive monitoring stopped by user.")
        finally:
             print("Exiting.")


if __name__ == "__main__":
    main()