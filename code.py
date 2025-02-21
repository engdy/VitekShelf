# RGB Light Driver for Vitek shelves
# Copyright 2025 Andy Foulke

import os
import ipaddress
import wifi
import socketpool
import board
import pwmio
import time
import digitalio
import microcontroller
from adafruit_httpserver import Server, Request, Response, REQUEST_HANDLED_RESPONSE_SENT, GET

# Recall most recent RGB values from non-volatile memory
current_rgb_b = microcontroller.nvm[0:3]
current_rgb = int.from_bytes(current_rgb_b, 'big')
current_r = current_rgb // 65536
current_g = (current_rgb // 256) % 256
current_b = current_rgb % 256

# Configure pins 14, 15, 16 to be LED driver pins
rled = pwmio.PWMOut(board.GP14, frequency=1000)
gled = pwmio.PWMOut(board.GP15, frequency=1000)
bled = pwmio.PWMOut(board.GP16, frequency=1000)

# Configure pin 13 to be on/off toggle
button = digitalio.DigitalInOut(board.GP13)
button.switch_to_input(pull=digitalio.Pull.DOWN)

# Start pulse width modulation on LED driver pins to get light shining
rled.duty_cycle = (current_rgb // 65536) * 256
gled.duty_cycle = ((current_rgb // 256) % 256) * 256
bled.duty_cycle = (current_rgb % 256) * 256

# Connect to Wi-Fi using credentials in separate settings.toml file
wifi.radio.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))

pool = socketpool.SocketPool(wifi.radio)

server = Server(pool, "/static")

# Default route just responds with "Vitek Shelf: RRGGBB"
# where RRGGBB is current RGB setting in hex. Client can use this to confirm correct connection, and
# to initialize client display
@server.route("/")
def base(request: Request):
    global current_r
    global current_b
    global current_g
    return Response(request, f"Vitek Shelf: {current_r:02x}{current_g:02x}{current_b:02x}{current_on_off:02x}")

# Client does HTTP GET supplying new R,G,B values to change color. Ex:
# http://192.168.1.3:5000/change-color?r=109&g=63&b=3
@server.route("/change-color", GET)
def change_color_handler(request: Request):
    global current_r
    current_r = int(request.query_params.get("r")) or 0
    global current_g
    current_g = int(request.query_params.get("g")) or 0
    global current_b
    current_b = int(request.query_params.get("b")) or 0
    global current_rgb
    current_rgb = int(current_r) * 65536 + int(current_g) * 256 + int(current_b)
    # Make sure this new setting is stored in non-volatile memory so color will resume on next powerup
    microcontroller.nvm[0:3] = current_rgb.to_bytes(3, 'big')
    rled.duty_cycle = int(current_r) * 256
    gled.duty_cycle = int(current_g) * 256
    bled.duty_cycle = int(current_b) * 256
    return Response(request, f"Changed color to ({current_r}, {current_g}, {current_b})")

# Listen on port 5000
server.start(str(wifi.radio.ipv4_address), 5000)

while True:
    if button.value:
        print("Pressed")
    try:
        pool_result = server.poll()
        if pool_result == REQUEST_HANDLED_RESPONSE_SENT:
            pass
    except OSError as error:
        print(error)
        continue
    time.sleep(0.1)
