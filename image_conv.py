import time
import board
import busio
import pygame
import numpy as np
import adafruit_mlx90640
from scipy.ndimage import convolve  # <--- Import pour le lissage ultra-rapide

# =========================================================
# CONFIGURATION
# =========================================================
WIDTH, HEIGHT = 32, 24
PIXELS = WIDTH * HEIGHT
SCALE = 20
WIN_W, WIN_H = WIDTH * SCALE, HEIGHT * SCALE

ALPHA = 0.5  # Filtre temporel (0.1 = lent/stable, 0.9 = rapide/bruité)
dynamic_min = 20.0
dynamic_max = 35.0

# --- Masque Gaussien 3x3 pour Scipy ---
GAUSSIAN_KERNEL = np.array([
    [1, 2, 1],
    [2, 4, 2],
    [1, 2, 1]
], dtype=np.float32) / 16.0

# =========================================================
# PYGAME & PALETTE
# =========================================================
pygame.init()
screen = pygame.display.set_mode((WIN_W + 100, WIN_H))
pygame.display.set_caption("MLX90640 - Scipy Fast Smoothing")
font = pygame.font.SysFont(None, 22)
surface = pygame.Surface((WIDTH, HEIGHT))

def generate_palette():
    key_colors = np.array([
        (0, 0, 0), (45, 0, 135), (147, 0, 149),
        (241, 33, 11), (255, 126, 0), (255, 206, 0), (255, 255, 255)
    ], dtype=np.float32)
    palette = np.zeros((256, 3), dtype=np.uint8)
    segments = len(key_colors) - 1
    steps = 256 // segments
    idx = 0
    for i in range(segments):
        c1, c2 = key_colors[i], key_colors[i + 1]
        for s in range(steps):
            palette[idx] = c1 + (c2 - c1) * s / steps
            idx += 1
    palette[idx:] = palette[idx - 1]
    return palette

PALETTE = generate_palette()

# =========================================================
# MLX90640
# =========================================================
try:
    i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
    print("Capteur MLX90640 connecté à 8Hz.")
except Exception as e:
    print("Erreur :", e)
    exit()

# =========================================================
# BUFFERS
# =========================================================
frame = np.zeros(PIXELS, dtype=np.float32)
filtered_frame = np.zeros(PIXELS, dtype=np.float32)
first_run = True

# =========================================================
# BOUCLE PRINCIPALE
# =========================================================
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    try:
        # 1. Acquisition
        mlx.getFrame(frame)
        
        # 2. Filtre Temporel (Lissage entre les images successives)
        if first_run:
            filtered_frame[:] = frame
            first_run = False
        else:
            # Vectorisation NumPy pour la rapidité
            filtered_frame[:] = filtered_frame * (1 - ALPHA) + frame * ALPHA

        # 3. FILTRE SPATIAL RAPIDE (Scipy)
        # On transforme en matrice 2D, on convolve, et on remet à plat
        matrix = filtered_frame.reshape((HEIGHT, WIDTH))
        # mode='reflect' gère proprement les pixels sur les bords
        smoothed_matrix = convolve(matrix, GAUSSIAN_KERNEL, mode='reflect')
        display_data = smoothed_matrix.flatten()

        # 4. Calcul des stats et dynamique
        rmin, rmax = display_data.min(), display_data.max()
        dynamic_min = 0.9 * dynamic_min + 0.1 * rmin
        dynamic_max = 0.9 * dynamic_max + 0.1 * rmax

    except ValueError: # Erreur de lecture I2C commune avec ce capteur
        continue
    except Exception as e:
        print(f"Erreur : {e}")
        break

    # =====================================================
    # RENDU (Vectorisé)
    # =====================================================
    # Mapping Température -> Index Palette (0-255)
    idx = ((display_data - dynamic_min) * 255.0 / (dynamic_max - dynamic_min + 1e-6))
    idx = np.clip(idx, 0, 255).astype(np.uint8)

    # Création de l'image RGB
    rgb = PALETTE[idx].reshape(HEIGHT, WIDTH, 3)
    rgb = np.flip(rgb, axis=1) # Miroir horizontal
    rgb = np.transpose(rgb, (1, 0, 2)) # Adaptation format Pygame

    # Affichage
    pygame.surfarray.blit_array(surface, rgb)
    scaled = pygame.transform.smoothscale(surface, (WIN_W, WIN_H))
    screen.blit(scaled, (0, 0))

    # Interface UI
    pygame.draw.rect(screen, (30, 30, 30), (WIN_W, 0, 100, WIN_H))
    screen.blit(font.render(f"MAX: {rmax:.1f}", True, (255,100,100)), (WIN_W + 15, 20))
    screen.blit(font.render(f"MIN: {rmin:.1f}", True, (100,100,255)), (WIN_W + 15, WIN_H - 40))

    pygame.display.flip()

pygame.quit()