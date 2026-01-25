#!/bin/bash
set -e
VENV_NAME="env_test2"

# 1. Mise à jour du système
echo "--- Mise à jour du système ---"
sudo apt-get update && sudo apt-get -y upgrade
sudo apt install --upgrade python3-setuptools -y


# 2. Installation de Python3 et venv s'ils ne sont pas présents
echo "--- Installation de Python et des outils de base ---"
sudo apt-get install -y python3 python3-pip python3-venv

# 3. Création de l'environnement virtuel
echo "--- 2. Création de l'environnement virtuel ($VENV_NAME) ---"
if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv $VENV_NAME
fi

# 4. Activation et installation des bibliothèques
echo "--- Installation de Blinka et des dépendances ---"
source $VENV_NAME/bin/activate
cd $VENV_NAME
pip3 install --upgrade adafruit-python-shell
pip install --upgrade pip
wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py
echo "n" | sudo -E env PATH=$PATH python3 raspi-blinka.py

pip3 install adafruit-circuitpython-mlx90640
pip3 install numpy pygame matplotlib scipy cmapy lgpio

# 5. Création des fichiers Python
echo "--- Création des fichiers .py ---"
cat <<EOF > test_blinka.py
import board
import digitalio
import busio

print("Hello, blinka!")

# Try to create a Digital input
pin = digitalio.DigitalInOut(board.D4)
print("Digital IO ok!")

# Try to create an I2C device
i2c = busio.I2C(board.SCL, board.SDA)
print("I2C ok!")

# Try to create an SPI device
spi = busio.SPI(board.SCLK, board.MOSI, board.MISO)
print("SPI ok!")

print("done!")
EOF

cat <<EOF > image.py
import time
import board
import busio
import pygame
import numpy as np
import adafruit_mlx90640
# cmapy non appelée directement mais nécessaire à installer via pip3 install 
#import cmapy 
import matplotlib.pyplot as plt
from scipy.ndimage import convolve

# =========================================================
# CONFIGURATION
# =========================================================
WIDTH, HEIGHT = 32, 24
SCALE = 20
WIN_W, WIN_H = WIDTH * SCALE, HEIGHT * SCALE

ALPHA = 0.5  
dynamic_min = 20.0
dynamic_max = 35.0

# Masque Gaussien 3x3, les forces de chaque pixels sont ajustables.
GAUSSIAN_KERNEL = np.array([
    [1, 2, 1],
    [2, 4, 2],
    [1, 2, 1]
], dtype=np.float32) / 16.0

# =========================================================
# CREATION PALETTE DE COULEURS
# =========================================================
# Liste des palettes disponibles dans cmapy
PALETTE_NAMES = ['jet','bwr','seismic','coolwarm','PiYG_r','tab10','tab20','gnuplot2','brg']
current_palette_idx = 0

# Récupère une plaette RGBA mais ne garde que le RGB
def get_pygame_palette(name):
    cmap = plt.get_cmap(name)
    indices = np.linspace(0, 1, 256)
    rgb_colors = (cmap(indices)[:, :3] * 255).astype(np.uint8)
    return rgb_colors

# Initialisation de la première palette
PALETTE = get_pygame_palette(PALETTE_NAMES[current_palette_idx])

# =========================================================
# INITIALISATION PYGAME & MATÉRIEL
# =========================================================
pygame.init()
screen = pygame.display.set_mode((WIN_W + 120, WIN_H))
pygame.display.set_caption("Appuyez sur C pour changer de palette - ESC pour stopper")
font = pygame.font.SysFont(None, 24)
surface = pygame.Surface((WIDTH, HEIGHT))
# Initialisation de la caméra
# Fréquence I2C gérée par /boot/firmware/config.txt (recommandé: 400000)
i2c = busio.I2C(board.SCL, board.SDA)
mlx = adafruit_mlx90640.MLX90640(i2c)
#Refresh Rate à fixer
mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ

# Crétation de la frame vide pour recevoir les données de get_frame
frame = np.zeros(WIDTH * HEIGHT)
filtered_matrix = np.full((HEIGHT, WIDTH), 25.0)

# =========================================================
# BOUCLE PRINCIPALE
# =========================================================
running = True
while running:
    t0 = time.time()
    for event in pygame.event.get():
        
        # on tape 'c' pour changer de palette
        # on tape 'ESC' pour arrêter le programme
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.display.quit()
                pygame.quit()
                running = False

            if event.key == pygame.K_c:
                current_palette_idx = (current_palette_idx + 1) % len(PALETTE_NAMES)
                new_name = PALETTE_NAMES[current_palette_idx]
                PALETTE = get_pygame_palette(new_name)
                print(f"Palette changée pour : {new_name}")

    try:
        # Prend la frame de température déjà calculé par la libraire adafruit
        mlx.getFrame(frame)
        raw_matrix = frame.reshape((HEIGHT, WIDTH))
        
        # Filtre 1 : Prend une partie de l'ancienne image pour faire la nouvelle
        # Filtre 2 : on fait le produit de convolution de l'image par la matrice gaussienne définié plis haut
        filtered_matrix = filtered_matrix * (1 - ALPHA) + raw_matrix * ALPHA
        smoothed = convolve(filtered_matrix, GAUSSIAN_KERNEL, mode='reflect')
        
        # calcul des températures grâce à Numpy
        # On prend l'ancienne température maximale et minimale pour lisser sur le temps
        # On peut avoir moins de lissage en augmentant le facteur devant rmin et rmax
        # et en abaissant le facteur devant dynamic_min et dynamic_max. 
        #  La somme doit faire 1.
        rmin, rmax = smoothed.min(), smoothed.max()
        dynamic_min = 0.9 * dynamic_min + 0.1 * rmin
        dynamic_max = 0.9 * dynamic_max + 0.1 * rmax

        # Produit en croix pour faire devenir les pixels de la température la plus basse '0' et les pixels les plus chauds '1'
        # Puis on multiplie par 255 pour créer un index
        # le 0.000001 est là pour éviter une division par 0 car lorsque le capteur et couvert le mix et le max devienne égaux
        idx = ((smoothed - dynamic_min) * 255.0 / (dynamic_max - dynamic_min + 1e-6))
        idx = np.clip(idx, 0, 255).astype(np.uint8)

        # Colorisation du frame
        # On inverse l'image
        rgb_array = PALETTE[idx]
        rgb_array = np.flip(rgb_array, axis=1)
        pygame_format = np.transpose(rgb_array, (1, 0, 2))

        # Affichage de l'image
        pygame.surfarray.blit_array(surface, pygame_format)
        scaled = pygame.transform.smoothscale(surface, (WIN_W, WIN_H))
        screen.blit(scaled, (0, 0))

        # --- Barre latérale et texte ---
        pygame.draw.rect(screen, (30, 30, 30), (WIN_W, 0, 120, WIN_H))
        
        # Dessiner la petite barre de l'échelle actuelle
        for i in range(256):
            y_p = WIN_H - 50 - (i * (WIN_H-100) / 255)
            pygame.draw.line(screen, PALETTE[i], (WIN_W + 20, y_p), (WIN_W + 40, y_p))

        fps = 1.0 / (time.time() - t0)
        
        # affichage de la temp_max, min et du nom de la palette utilisée
        screen.blit(font.render(PALETTE_NAMES[current_palette_idx].upper(), True, (255, 255, 255)), (WIN_W + 15, WIN_H-15))
        screen.blit(font.render(f"{dynamic_max:.1f}", True, (255,255,255)), (WIN_W + 15, 20))
        screen.blit(font.render(f"{dynamic_min:.1f}", True, (255,255,255)), (WIN_W + 15, WIN_H - 40))


    except Exception as e:
        print(f"Erreur : {e}")
        continue

    pygame.display.flip()

pygame.quit()


EOF

cat <<EOF > monitoring.py
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


EOF

# 6. Fin de l'installation
echo "Installation terminée ! "
echo " Redémarrage..."

sudo reboot
