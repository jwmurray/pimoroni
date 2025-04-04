All the python code other than monitor.py should be copied to the Pimoroni pico plus 2w

On the linux box, run the monitor.py file.  To do this, 

1. Install the system requirements
```
uv env                       # create the pip virtual environment using uv
source .venv/bin/activate    # activate pip virtual environment
uv pip install requests matplotlib numpy  # install the python libraries using uv

