All the python code other than monitor.py should be copied to the Pimoroni pico plus 2w

On the linux box, run the monitor.py file.  To do this, 

1. Install the system requirements
```
uv env                       # create the pip virtual environment using uv
source .venv/bin/activate    # activate pip virtual environment
uv pip install requests matplotlib numpy  # install the python libraries using uv


## Altitude Calculation: 
The altitude is derived using the barometric formula. This formula describes how atmospheric pressure decreases as altitude increases, assuming certain standard atmospheric conditions (like temperature lapse rate). A commonly used simplified version is:
Altitude = 44330 × ( 1 - (P/P₀)^^(1/5.255))

Where:
Altitude is in meters.
P is the measured barometric pressure (e.g., in Pascals).
P₀ is the standard atmospheric pressure at mean sea level (typically fixed at 101325 Pa).
The constants (44330 and 1/5.255) relate to standard temperature, gravity, and air composition assumptions.