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