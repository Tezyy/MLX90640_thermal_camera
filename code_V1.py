import time
import board
import busio
import adafruit_mlx90640


# --- CONFIGURATION ---
ALARM_THRESHOLD = 20.0  # Temperature to trigger alarm (Celsius)
DISTANCE_MODE = True    # Set to True to enable a simple noise filter for distance
PRINT_TEMPERATURES = False # Set to tru to enable temperature printing
PRINT_ASCIIART = False # Set to true to enable asciiart printing
REQUIRED_DURATION = 30.0    # Temps cumulé au-dessus du seuil
GRACE_PERIOD = 5.0          # Temps de tolérance avant de réinitialiser le timer

overheat_accumulator = 0.0  # Temps total passé en surchauffe
last_check_time = time.monotonic()
last_high_temp_time = None  # Moment où on a vu une température haute pour la dernière fois
alarm_active = False

i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
mlx = adafruit_mlx90640.MLX90640(i2c)
print("MLX addr detected on I2C")

# Set refresh rate (2Hz or 4Hz is best for distance to reduce noise)
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ

frame = [0] * 768

def get_max_temp_filtered(frame_data, threshold=ALARM_THRESHOLD):
    max_detected = -100.0 
    neighbor_threshold = threshold - 5.0  # Un voisin est tiède
    
    for y in range(24):
        for x in range(32):
            index = y * 32 + x
            val = frame_data[index]
            
            # Si le pixel actuel dépasse notre maximum temporaire
            if val > max_detected:
                
                # Vérifier les 4 voisins directs
                is_valid = False
                # Voisins : (x+1, y), (x-1, y), (x, y+1), (x, y-1)
                # si on veut inclure les diagonales, on rajoute à la liste
                # (1,1), (1,-1), (-1,1), (-1,-1)
                for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                    nx, ny = x + dx, y + dy
                    # Vérifier si le voisin est bien dans la grille
                    if 0 <= nx < 32 and 0 <= ny < 24:
                        n_index = ny * 32 + nx
                        if frame_data[n_index] > neighbor_threshold:
                            is_valid = True
                            break # Un seul voisin chaud suffit
                
                # Si le pixel est validé par un voisin ou si on n'est pas encore au seuil d'alerte
                if is_valid :#and val>=threshold:
                    max_detected = val
                    
    return max_detected

while True:
    now = time.monotonic()
    dt = now - last_check_time  # Temps écoulé depuis la dernière boucle
    last_check_time = now
    try:
        mlx.getFrame(frame)
    except ValueError:
        continue
    
    max_temp = get_max_temp_filtered(frame, threshold=ALARM_THRESHOLD)
    avg_temp = sum(frame) / len(frame)
    status = "NORMAL"

    if max_temp >= ALARM_THRESHOLD:
        # On est au-dessus du seuil, on cumule le temps
        overheat_accumulator += dt
        last_high_temp_time = now
        
        if overheat_accumulator >= REQUIRED_DURATION and not alarm_active:
            alarm_active = True
            print(f"!!! ALERTE CONFIRMÉE : {max_temp:.1f}°C stables !!!")
        elif not alarm_active:
            print(f"Accumulation : {overheat_accumulator:.1f}s / {REQUIRED_DURATION}s")
    
    else:
        # On est en dessous du seuil
        if last_high_temp_time is not None:
            time_since_last_high = now - last_high_temp_time
            
            if time_since_last_high > GRACE_PERIOD:
                # Cela fait trop longtemps qu'on est en dessous, on réinitialise
                if overheat_accumulator > 0:
                    print("Température basse prolongée. Réinitialisation du timer.")
                overheat_accumulator = 0.0
                last_high_temp_time = None
                alarm_active = False
            else:
                # On est en dessous, mais on attend de voir si ça remonte (Grace Period)
                print(f"Baisse temporaire... on maintient le timer ({overheat_accumulator:.1f}s)")

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
