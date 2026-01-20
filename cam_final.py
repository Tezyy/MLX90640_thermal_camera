import time
import board
import busio
import adafruit_mlx90640


# --- CONFIGURATION ---
ALARM_THRESHOLD = 20.0  # Temperature to trigger alarm (°C)
NEIGHBOR_THRESHOLD = ALARM_THRESHOLD - 5 # Tolerated temperature of hot spot neighbors
REQUIRED_DURATION = 30.0    # Cumulative duration above threshold (seconds)
GRACE_PERIOD = 5.0          # Tolerance delay before resetting timer
MIN_HOT_PIXELS = 1  # Minimum number of hot pixels to trigger alarm
PRINT_TEMPERATURES = False # Enable temperature display
PRINT_ASCIIART = False # Enable ASCII art display

overheat_accumulator = 0.0  # Total time spent in overheat status
last_check_time = time.monotonic()
last_high_temp_time = None  # Last time a high temperature was detected
alarm_active = False

i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
mlx = adafruit_mlx90640.MLX90640(i2c)
print("MLX addr detected on I2C")

# Camera refresh rate. (above 4Hz requires increasing i2c baudrate)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_1_HZ

frame = [0] * 768
# --- get_max_temp_filtered ---
def get_max_temp_filtered(frame_data, threshold=ALARM_THRESHOLD):
    max_detected = -100.0 
    hot_pixels_list = []  # List of all detected hot spots
    neighbor_threshold = threshold - 5.0  # A neighbor is considered "warm"
    
    for y in range(24):
        for x in range(32):
            index = y * 32 + x
            val = frame_data[index]
            
            # Ignore cold pixels (below threshold)
            if val > threshold:            
                # Check the 4 direct neighbors
                hot_neighbors = 0
                for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < 32 and 0 <= ny < 24:
                        n_index = ny * 32 + nx
                        if frame_data[n_index] > neighbor_threshold:
                            hot_neighbors += 1
            
                # Require at least 2 warm neighbors
                if hot_neighbors >= 2:
                    if val > max_detected:
                        max_detected = val
                    hot_pixels_list.append(val)
    
    # Return: max_temp, hot spot count, hot spot average
    avg_hot = sum(hot_pixels_list) / len(hot_pixels_list) if hot_pixels_list else -100.0
    hot_count = len(hot_pixels_list)
    return max_detected, hot_count, avg_hot

# --- MAIN LOOP ---
while True:
    now = time.monotonic()
    dt = now - last_check_time  # Elapsed time since last loop
    last_check_time = now
    try:
        mlx.getFrame(frame)
    except ValueError:
        continue
    
    max_temp, hot_pixels_count, avg_hot_temp = get_max_temp_filtered(frame, threshold=ALARM_THRESHOLD)
    avg_temp = sum(frame) / len(frame)
    status = "NORMAL"

    if max_temp >= ALARM_THRESHOLD and hot_pixels_count >= MIN_HOT_PIXELS:
        # Above threshold with enough hot pixels
        overheat_accumulator += dt
        last_high_temp_time = now
        
        if overheat_accumulator >= REQUIRED_DURATION and not alarm_active:
            alarm_active = True
            print(f"!!! ALARM CONFIRMED : {max_temp:.1f}°C ({hot_pixels_count} hot pixels) !!!")
        elif not alarm_active:
            print(f"Accumulating : {overheat_accumulator:.1f}s / {REQUIRED_DURATION}s | {hot_pixels_count} pixels @ {max_temp:.1f}°C (avg: {avg_hot_temp:.1f}°C)")
    
    else:
        # Below threshold
        if last_high_temp_time is not None:
            time_since_last_high = now - last_high_temp_time
            
            if time_since_last_high > GRACE_PERIOD:
                # Below threshold for too long, reset everything
                print(f"Prolonged low temperature ({time_since_last_high:.1f}s). Resetting timer.")
                overheat_accumulator = 0.0
                last_high_temp_time = None
                alarm_active = False
            else:
                # Below threshold, but waiting to see if it goes back up (GRACE_PERIOD)
                print(f"Temporary drop... maintaining timer ({overheat_accumulator:.1f}s / {REQUIRED_DURATION}s - grace: {time_since_last_high:.1f}s)")

    time.sleep(0.1)
    
    # Print grid output
    print(f"Status: {status: <25} | Max Temp: {max_temp:.1f}C | Avg Temp: {avg_temp:.1f}C")
    for h in range(24):
        for w in range(32):
            t = frame[h * 32 + w]
            if PRINT_TEMPERATURES:
                print("%0.1f, " % t, end="")
            if PRINT_ASCIIART:
                c = "&"
                if t < 20:
                    c = " "
                elif t < 23:
                    c = "."
                elif t < 25:
                    c = "-"
                elif t < 27:
                    c = "*"
                elif t < 29:
                    c = "+"
                elif t < 31:
                    c = "x"
                elif t < 33:
                    c = "%"
                elif t < 35:
                    c = "#"
                elif t < 37:
                    c = "X"
                print(c, end="")