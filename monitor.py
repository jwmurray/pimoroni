#! /usr/bin/env python3

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

class SensorMonitor:
    def __init__(self, server_url, update_interval=5, max_points=300, time_window_minutes=6):
        self.server_url = server_url
        self.update_interval = update_interval
        self.max_points = max_points
        self.time_window_minutes = time_window_minutes
        self.time_window_seconds = time_window_minutes * 60
        
        # Initialize data storage
        self.timestamps = deque(maxlen=max_points)
        self.temperature_data = deque(maxlen=max_points)
        self.pressure_data = deque(maxlen=max_points)
        self.humidity_data = deque(maxlen=max_points)
        self.altitude_data = deque(maxlen=max_points)
        
        # Min/max values for each sensor
        self.ranges = {
            'temperature': {'min': float('inf'), 'max': float('-inf')},
            'pressure': {'min': float('inf'), 'max': float('-inf')},
            'humidity': {'min': float('inf'), 'max': float('-inf')},
            'altitude': {'min': float('inf'), 'max': float('-inf')}
        }
        
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
        """Update the min/max ranges for each sensor type with nice round boundaries"""
        axes = [self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt]
        formatters = [format_temp_humid, format_pressure, format_temp_humid, format_altitude]
        data_sets = [self.temperature_data, self.pressure_data, self.humidity_data, self.altitude_data]
        keys = ['temperature', 'pressure', 'humidity', 'altitude']
        
        for i, (ax, data, key, formatter) in enumerate(zip(axes, data_sets, keys, formatters)):
            if data:
                # Update min/max values
                current_min = min(data)
                current_max = max(data)
                self.ranges[key]['min'] = min(current_min, self.ranges[key]['min'])
                self.ranges[key]['max'] = max(current_max, self.ranges[key]['max'])
                
                # Calculate nice round boundaries for y-axis
                data_range = self.ranges[key]['max'] - self.ranges[key]['min']
                if data_range == 0: # Handle case where all data points are the same
                     min_val = self.ranges[key]['min'] - 1
                     max_val = self.ranges[key]['max'] + 1
                else:
                    # Round min down and max up to appropriate precision
                    if key == 'temperature' or key == 'humidity':
                        min_val = np.floor(self.ranges[key]['min'] * 2) / 2 - 0.5 # Add small buffer
                        max_val = np.ceil(self.ranges[key]['max'] * 2) / 2 + 0.5 # Add small buffer
                    elif key == 'pressure':
                        step = 100
                        min_val = np.floor(self.ranges[key]['min'] / step) * step - step
                        max_val = np.ceil(self.ranges[key]['max'] / step) * step + step
                    else:  # altitude
                        step = 10
                        min_val = np.floor(self.ranges[key]['min'] / step) * step - step
                        max_val = np.ceil(self.ranges[key]['max'] / step) * step + step
                    
                    # Add a small margin if min and max are still identical after rounding
                    if abs(max_val - min_val) < 1e-6:
                        min_val -= 1
                        max_val += 1
                        
                # Update y-axis limits and ticks
                ax.set_ylim(min_val, max_val)
                tick_range = max_val - min_val
                num_ticks = 5 # Aim for around 5 major ticks
                
                if key == 'temperature':
                    if tick_range <= 2: major_step, minor_step = 0.5, 0.1
                    elif tick_range <= 5: major_step, minor_step = 1.0, 0.2
                    elif tick_range <= 10: major_step, minor_step = 2.0, 0.5
                    else: major_step, minor_step = 5.0, 1.0
                elif key == 'pressure':
                    major_step = max(100, np.ceil(tick_range / num_ticks / 100) * 100)
                    minor_step = major_step / 4
                elif key == 'humidity':
                    if tick_range <= 5: major_step, minor_step = 1, 0.2
                    elif tick_range <= 10: major_step, minor_step = 2, 0.5
                    else: major_step, minor_step = max(5, np.ceil(tick_range / num_ticks / 5)*5), 1
                else: # altitude
                    major_step = max(10, np.ceil(tick_range / num_ticks / 10) * 10)
                    minor_step = major_step / 5
                    
                ax.yaxis.set_major_locator(plt.MultipleLocator(major_step))
                ax.yaxis.set_minor_locator(plt.MultipleLocator(minor_step))
                ax.yaxis.set_major_formatter(FuncFormatter(formatter))
    
    def setup_plot(self):
        """Set up the plot with 4 subplots"""
        plt.rcParams['axes.formatter.useoffset'] = False
        
        # Create 4 subplots, sharing the x-axis
        self.fig, axs = plt.subplots(4, 1, sharex=True, figsize=(12, 10))
        self.ax_temp, self.ax_press, self.ax_humid, self.ax_alt = axs # Unpack axes
        
        # Disable offset for all axes to ensure absolute values are shown
        for ax in axs:
            ax.ticklabel_format(useOffset=False, style='plain') # Use plain style
            ax.grid(True, linestyle='--', alpha=0.7)

        # Set colors (optional, but can be nice)
        self.temp_color = 'red'
        self.press_color = 'blue' 
        self.humid_color = 'green'
        self.alt_color = 'purple'
        
        # Create empty line objects on their respective axes
        self.temp_line, = self.ax_temp.plot([], [], color=self.temp_color)
        self.press_line, = self.ax_press.plot([], [], color=self.press_color)
        self.humid_line, = self.ax_humid.plot([], [], color=self.humid_color)
        self.alt_line, = self.ax_alt.plot([], [], color=self.alt_color)
        
        # Set titles and labels for each subplot
        self.ax_temp.set_title('Temperature')
        self.ax_temp.set_ylabel('Temp (°F)')
        self.ax_press.set_title('Barometric Pressure')
        self.ax_press.set_ylabel('Pressure (Pa)')
        self.ax_humid.set_title('Humidity')
        self.ax_humid.set_ylabel('Humidity (%)')
        self.ax_alt.set_title('Altitude')
        self.ax_alt.set_ylabel('Altitude (ft)')
        
        # Only the bottom plot needs the x-axis label
        self.ax_alt.set_xlabel('Time')
        
        # Add main title
        self.fig.suptitle('Real-time Sensor Data from Pico', fontsize=16, y=0.98)
        
        plt.tight_layout()
        # Adjust layout to prevent titles overlapping
        self.fig.subplots_adjust(top=0.92, hspace=0.4)
        
    def format_x_axis(self, x_data):
        """Format x-axis based on the time range"""
        max_time = x_data[-1] if len(x_data) > 0 else 0
        
        # Set the time display window (either elapsed time or fixed window)
        x_max = max(max_time + 30, self.time_window_seconds)
        # Set xlim only on one axis (since they are shared)
        self.ax_temp.set_xlim(0, x_max)
        
        # Get the bottom axis for formatting
        bottom_ax = self.ax_alt
        
        # Format x-axis ticks based on the range
        if x_max <= 600:  # Less than 10 minutes
            bottom_ax.xaxis.set_major_locator(plt.MultipleLocator(60))
            bottom_ax.xaxis.set_minor_locator(plt.MultipleLocator(15))
            bottom_ax.set_xlabel('Time (seconds)')
        elif x_max <= 7200:  # Less than 2 hours
            bottom_ax.xaxis.set_major_locator(plt.MultipleLocator(600))
            bottom_ax.xaxis.set_minor_locator(plt.MultipleLocator(60))
            bottom_ax.set_xlabel('Time (minutes)')
        else:  # More than 2 hours
            bottom_ax.xaxis.set_major_locator(plt.MultipleLocator(3600))
            bottom_ax.xaxis.set_minor_locator(plt.MultipleLocator(600))
            bottom_ax.set_xlabel('Time (hours)')
            
        # Add custom formatter to show time in appropriate units
        def format_time(x, pos):
            if x_max <= 600: return f"{int(x)}s"
            elif x_max <= 7200: return f"{int(x/60)}m"
            else: return f"{int(x/3600)}h"
                
        bottom_ax.xaxis.set_major_formatter(plt.FuncFormatter(format_time))
        
    def update_plot(self, frame):
        """Update function for animation"""
        # Fetch new data
        data = self.fetch_sensor_data()
        if data:
            current_time = datetime.now()
            self.timestamps.append(current_time)
            
            # Extract sensor values
            self.temperature_data.append(data.get('temperature', 0))
            self.pressure_data.append(data.get('barometric_pressure', 0))
            self.humidity_data.append(data.get('humidity', 0))
            self.altitude_data.append(data.get('altitude', 0))
            
            # Update the data ranges and y-axis limits/ticks/labels
            self.update_data_ranges()
            
            # Update the plot data
            x_data = np.array([(t - self.timestamps[0]).total_seconds() for t in self.timestamps])
            if not len(x_data): # Skip if no data yet
                return self.temp_line, self.press_line, self.humid_line, self.alt_line
            
            self.temp_line.set_data(x_data, np.array(self.temperature_data))
            self.press_line.set_data(x_data, np.array(self.pressure_data))
            self.humid_line.set_data(x_data, np.array(self.humidity_data))
            self.alt_line.set_data(x_data, np.array(self.altitude_data))
            
            # Format x-axis based on time range
            self.format_x_axis(x_data)
            
            # Update the main title with the last reading
            reading_title = (f'Temp: {self.temperature_data[-1]:.1f}°F, '
                         f'Pressure: {self.pressure_data[-1]:.0f}Pa, '
                         f'Humidity: {self.humidity_data[-1]:.1f}%, '
                         f'Altitude: {self.altitude_data[-1]:.0f}ft')
            self.fig.suptitle(f'Real-time Sensor Data from Pico\nLast Reading: {reading_title}', fontsize=14, y=0.98)
            
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
    parser.add_argument('--points', type=int, default=300,
                        help='Maximum number of data points to display')
    parser.add_argument('--time-window', type=float, default=6.0,
                        help='Time window to display in minutes (up to 2880 for 2 days)')
    
    args = parser.parse_args()
    
    # Validate interval
    if args.interval < 1 or args.interval > 3600:
        parser.error("Interval must be between 1 second and 3600 seconds (1 hour)")
        
    # Validate time window (up to 2 days)
    if args.time_window < 1 or args.time_window > 2880:
        parser.error("Time window must be between 1 minute and 2880 minutes (2 days)")
    
    print(f"Starting sensor monitor - connecting to {args.server}")
    print(f"Update interval: {args.interval}s, Time window: {args.time_window} minutes")
    monitor = SensorMonitor(args.server, args.interval, args.points, args.time_window)
    monitor.run()

if __name__ == "__main__":
    main()