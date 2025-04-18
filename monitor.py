#! /usr/bin/env python3

# Make sure that main.py is running on the pico.  Through thonny or automatically from boot.  


# Use this program, monitor.py on Ubuntu, do the following:
# sudo apt-get install python3-matplotlib
# sudo apt-get install python3-numpy
# sudo apt-get install python3-requests

# Install uv and create a virtual environment -- You can do this with pip alone, but life is better if you learn to use uv.
# curl -LsSf https://astral.sh/uv/install.sh | sh
# uv sync

# Create the virtual environment and install the dependencies at ./.venv
# uv venv

# Activate the virtual environment:
# source ./.venv/bin/activate

# Install the dependencies:
# uv pip install -r requirements.txt

# Run the program:  (besure to type in the ip address of the pico in place of the default 192.168.0.201 shown below)
# ./monitor.py --server 192.168.0.201

import argparse
import time
import json
import numpy as np
import requests
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator, FuncFormatter
from datetime import datetime, timedelta
from collections import deque
import math # Import math for ceiling calculation

# --- Formatting functions for Y-axis ticks ---
def format_temp_humid(value, pos):
    # Format with one decimal place
    return f'{value:.1f}'

def format_pressure(value, pos):
    # Format as integer
    return f'{int(value)}'

def format_altitude(value, pos):
    # Format as integer
    return f'{int(value)}'
# ---------------------------------------------

# --- Formatting function for X-axis time ticks ---
def format_xaxis_time(value, pos):
    """Formats matplotlib numerical date value to HH:MM:SS.s"""
    try:
        # Convert matplotlib float date to datetime object
        dt_object = mdates.num2date(value)
        # Format to include tenths of a second (microseconds / 100000)
        return dt_object.strftime('%H:%M:%S') + f'.{dt_object.microsecond // 100000}'
    except ValueError:
        # Handle cases where conversion might fail (e.g., out of range)
        return ""
# ---------------------------------------------

class SensorMonitor:
    def __init__(self, server_url, update_interval=5, 
                 time_window_minutes=1440, initial_time_window_minutes=6):
        self.server_url = server_url
        if not self.server_url.startswith('http'):  # If the user did not use a http:// or https://, prepend http://
            self.server_url = 'http://' + self.server_url

        self.update_interval = update_interval # seconds
        self.max_time_window_minutes = time_window_minutes
        self.max_time_window_seconds = time_window_minutes * 60
        self.initial_time_window_minutes = initial_time_window_minutes
        self.initial_time_window_seconds = initial_time_window_minutes * 60
        self.start_time = None # Will store the absolute start time

        # Calculate max_points needed based on max window and interval
        # Add a small buffer (e.g., 10%) just in case
        self.max_points = math.ceil((self.max_time_window_seconds / self.update_interval) * 1.1) 
        print(f"Calculated max_points to store: {self.max_points} (for {self.max_time_window_minutes} min window at {self.update_interval}s interval)")

        # Initialize data storage with calculated max_points
        self.timestamps = deque(maxlen=self.max_points)
        self.temperature_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)
        self.humidity_data = deque(maxlen=self.max_points)
        self.altitude_data = deque(maxlen=self.max_points)
        
        # Setup plot with 4 subplots
        self.setup_plot()
        
    def fetch_sensor_data(self):
        """Fetch data from the Pico API server"""
        try:
            response = requests.get(f"{self.server_url}/sensor")
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                print(f"Error: API returned status code {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Connection error: {e}")
            return None
            
    def update_data_ranges(self):
        """Update the y-axis limits based on 10% padding around the current data range."""
        axes = [self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt]
        formatters = [format_temp_humid, format_pressure, format_temp_humid, format_altitude]
        data_sets = [self.temperature_data, self.pressure_data, self.humidity_data, self.altitude_data]
        keys = ['temperature', 'pressure', 'humidity', 'altitude'] # Keep keys for tick logic
        
        for i, (ax, data, key, formatter) in enumerate(zip(axes, data_sets, keys, formatters)):
            if data:
                # Calculate min/max from current data in the deque
                current_min = min(data)
                current_max = max(data)
                
                # Calculate range and buffer (10%)
                data_range = current_max - current_min
                
                if data_range < 1e-6: # Handle case where range is zero or very small
                    # Add a small absolute buffer based on typical scale
                    if key == 'temperature' or key == 'humidity': buffer = 0.5 
                    elif key == 'pressure': buffer = 50
                    else: buffer = 5 # altitude
                    min_val = current_min - buffer
                    max_val = current_max + buffer
                else:
                    buffer = data_range * 0.10 # 10% buffer
                    min_val = current_min - buffer
                    max_val = current_max + buffer

                # Update y-axis limits
                ax.set_ylim(min_val, max_val)
                
                # --- Tick logic: Ensure min/max are always labeled --- 
                tick_range = max_val - min_val
                num_ticks_target = 5 # Target number of ticks

                # Determine a reasonable major step based on the range
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

                # Generate intermediate ticks based on the step
                # Start slightly above min_val rounded to step, end slightly below max_val rounded to step
                start_tick = np.ceil(min_val / major_step) * major_step
                end_tick = np.floor(max_val / major_step) * major_step
                intermediate_ticks = np.arange(start_tick, end_tick + major_step * 0.5, major_step)

                # Combine min, max, and intermediate ticks, remove duplicates, and sort
                tick_locations = sorted(list(set([min_val] + list(intermediate_ticks) + [max_val])))

                # Filter out ticks that are too close together (e.g., closer than 1/10th of step)
                final_tick_locations = []
                if tick_locations:
                    final_tick_locations.append(tick_locations[0])
                    min_tick_spacing = major_step * 0.1
                    for i in range(1, len(tick_locations)):
                        if tick_locations[i] - final_tick_locations[-1] >= min_tick_spacing:
                            final_tick_locations.append(tick_locations[i])
                    
                # Use FixedLocator for major ticks
                ax.yaxis.set_major_locator(plt.FixedLocator(final_tick_locations))
                # Still use MultipleLocator for minor ticks
                ax.yaxis.set_minor_locator(plt.MultipleLocator(minor_step))
                ax.yaxis.set_major_formatter(FuncFormatter(formatter))
                # --- End of Tick logic ---
    
    def setup_plot(self):
        """Set up the plot with 4 subplots"""
        plt.rcParams['axes.formatter.useoffset'] = False
        
        # Create 4 subplots, sharing the x-axis
        self.fig, axs = plt.subplots(4, 1, sharex=True, figsize=(12, 10))
        self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt = axs
        
        # Disable offset and set grid for all axes
        for ax in axs:
            ax.ticklabel_format(useOffset=False, style='plain')
            ax.grid(True, linestyle='--', alpha=0.7)

        # Set colors
        self.temp_color = 'red'
        self.press_color = 'blue' 
        self.humid_color = 'green'
        self.alt_color = 'purple'
        
        # Create empty line objects
        self.temp_line, = self.ax_temp.plot([], [], color=self.temp_color)
        self.press_line, = self.ax_press.plot([], [], color=self.press_color)
        self.humid_line, = self.ax_humid.plot([], [], color=self.humid_color)
        self.alt_line, = self.ax_alt.plot([], [], color=self.alt_color)
        
        # Set titles and labels
        self.ax_temp.set_title('Temperature')
        self.ax_temp.set_ylabel('Temp (°F)')
        self.ax_press.set_title('Barometric Pressure')
        self.ax_press.set_ylabel('Pressure (Pa)')
        self.ax_humid.set_title('Humidity')
        self.ax_humid.set_ylabel('Humidity (%)')
        self.ax_alt.set_title('Altitude')
        self.ax_alt.set_ylabel('Altitude (ft)')
        
        # Initially set bottom x-axis label (will be updated)
        self.ax_alt.set_xlabel('Time')
        
        # Use AutoDateLocator to find tick positions automatically
        locator = mdates.AutoDateLocator(minticks=3, maxticks=10) # Allow more ticks for finer scale
        # Use our custom FuncFormatter for the labels
        formatter = FuncFormatter(format_xaxis_time)
        self.ax_alt.xaxis.set_major_locator(locator)
        self.ax_alt.xaxis.set_major_formatter(formatter)

        # Add main title
        self.fig.suptitle('Real-time Sensor Data from Pico', fontsize=16, y=0.98)
        
        plt.tight_layout()
        self.fig.subplots_adjust(top=0.92, hspace=0.4)
        
    def format_x_axis(self):
        """Format x-axis based on the current time range and window."""
        if not self.timestamps or not self.start_time:
            return
            
        # Get the latest timestamp
        end_time = self.timestamps[-1]
        
        # Calculate the start time for the view window
        view_start_time = max(
            self.start_time, 
            end_time - timedelta(seconds=self.max_time_window_seconds)
        )
        # Add a small buffer to the end_time for visibility
        view_end_time = end_time + timedelta(seconds=self.update_interval * 2)
        
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
            
            # Extract sensor values - updated to match new JSON format
            self.temperature_data.append(data.get('temperature_f', 0))
            self.pressure_data.append(data.get('pressure_pa', 0))
            self.humidity_data.append(data.get('humidity_percent', 0))
            self.altitude_data.append(data.get('altitude_ft', 0))
            
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
            reading_title = (f'Temp: {self.temperature_data[-1]:.1f}°F, '
                         f'Pressure: {self.pressure_data[-1]:.0f}Pa, '
                         f'Humidity: {self.humidity_data[-1]:.1f}%, '
                         f'Altitude: {self.altitude_data[-1]:.0f}ft')
            self.fig.suptitle(f'Real-time Sensor Data (Last Reading: {last_reading_time_str})\n{reading_title}', 
                            fontsize=14, y=0.98)
            
        # Return only the lines
        return self.temp_line, self.press_line, self.humid_line, self.alt_line
        
    def run(self):
        """Run the animation"""
        # Keep blit=False for robustness with subplots
        self.ani = animation.FuncAnimation(
            self.fig, self.update_plot, interval=self.update_interval*1000, blit=False) 
        plt.show()

def main():
    parser = argparse.ArgumentParser(description='Monitor Pico sensor data in real-time')
    parser.add_argument('--server', type=str, default='http://192.168.0.201',
                        help='URL of the Pico API server')
    parser.add_argument('--interval', type=float, default=5.0,
                        help='Update interval in seconds (1-3600)')
    parser.add_argument('--time-window', type=float, default=1440.0, 
                        help='Maximum time window to display in minutes (e.g., 1440 for 24 hours)')
    parser.add_argument('--initial-time-window', type=float, default=6.0, 
                        help='Initial time window to display in minutes (will expand up to max)')
    
    args = parser.parse_args()
    
    # Validate interval
    if args.interval < 1 or args.interval > 3600:
        parser.error("Interval must be between 1 second and 3600 seconds (1 hour)")
        
    # Validate time window (up to 2 days)
    if args.time_window < 1 or args.time_window > 2880:
        parser.error("Max time window must be between 1 minute and 2880 minutes (2 days)")
        
    # Validate initial time window
    if args.initial_time_window < 1 or args.initial_time_window > args.time_window:
        parser.error(f"Initial time window must be between 1 and the max time window ({args.time_window} minutes)")

    print(f"Starting sensor monitor - connecting to {args.server}")
    print(f"Update interval: {args.interval}s")
    print(f"Initial time window: {args.initial_time_window} minutes, Max time window: {args.time_window} minutes")
    monitor = SensorMonitor(args.server, args.interval, 
                            args.time_window, args.initial_time_window)
    monitor.run()

if __name__ == "__main__":
    main()