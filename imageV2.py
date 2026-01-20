import time
import board
import busio
import pygame
import adafruit_mlx90640

# --- 1. CONFIGURATION VISUELLE ---
WIDTH_CAM, HEIGHT_CAM = 32, 24
WINDOW_SCALE = 20  
WINDOW_WIDTH = WIDTH_CAM * WINDOW_SCALE
WINDOW_HEIGHT = HEIGHT_CAM * WINDOW_SCALE

# Initialisation des variables de calcul
rmin, rmax = 20.0, 35.0
dynamic_min, dynamic_max = 20.0, 35.0
frame = [0.0] * 768
frame2 = [0.0] * 768  # Deuxième frame
filtered_frame = [0.0] * 768
ALPHA = 0.9  # Lissage temporel (0.1 stable / 0.9 réactif)

# --- 2. INITIALISATION PYGAME ---
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH + 100, WINDOW_HEIGHT))
pygame.display.set_caption("Thermal Camera Pro - Auto-Contrast")
font = pygame.font.SysFont(None, 24)
sensor_surface = pygame.Surface((WIDTH_CAM, HEIGHT_CAM))

# --- 3. PALETTE DE COULEURS (IRONBOW 256) ---
COLORS = []
def generate_palette():
    # Dégradé : Noir -> Bleu -> Violet -> Rouge -> Orange -> Jaune -> Blanc
    key_colors = [(0,0,0), (45,0,135), (147,0,149), (241,33,11), (255,126,0), (255,206,0), (255,255,255)]
    segments = len(key_colors) - 1
    steps = 256 // segments
    for i in range(segments):
        c1, c2 = key_colors[i], key_colors[i+1]
        for s in range(steps):
            r = int(c1[0] + (c2[0]-c1[0])*s/steps)
            g = int(c1[1] + (c2[1]-c1[1])*s/steps)
            b = int(c1[2] + (c2[2]-c1[2])*s/steps)
            COLORS.append((r, g, b))
    while len(COLORS) < 256: COLORS.append((255, 255, 255))

generate_palette()

# --- 4. INITIALISATION CAPTEUR ---
mlx = None
try:
    # Fréquence I2C gérée par /boot/firmware/config.txt (recommandé: 400000)
    i2c = busio.I2C(board.SCL, board.SDA)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ 
    print("Capteur MLX90640 prêt.")
except Exception as e:
    print(f"Erreur matériel : {e}")

def map_value(x, in_min, in_max, out_min, out_max):
    if in_max == in_min: return out_min
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# --- 5. BOUCLE PRINCIPALE ---
running = True
first_run = True # Pour initialiser filtered_frame immédiatement

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if mlx:
        try:
            # Lecture de 2 frames
            mlx.getFrame(frame)
            mlx.getFrame(frame2)
            
            # Moyenne des 2 frames
            frame = [(frame[i] + frame2[i]) / 2 for i in range(768)]
            
            # Sécurité : Si le capteur renvoie des données vides
            if max(frame) == 0 and min(frame) == 0:
                continue

            # Mise à jour des stats
            rmin, rmax = min(frame), max(frame)
            print("rmax=\n",rmax)

            # Auto-ajustement fluide de l'échelle (vitesse 0.1)
            dynamic_min = (dynamic_min * 0.9) + (rmin * 0.1)
            dynamic_max = (dynamic_max * 0.9) + (rmax * 0.1)

            # Premier lancement : on remplit le filtre pour éviter l'écran noir (0°C)
            if first_run:
                filtered_frame = list(frame)
                first_run = False

            # Traitement des 768 pixels
            for i in range(768):
                # Filtre anti-scintillement
                filtered_frame[i] = (filtered_frame[i] * (1 - ALPHA)) + (frame[i] * ALPHA)
                
                # Coordonnées (inversées horizontalement)
                x, y = 31 - (i % 32), i // 32
                
                # Conversion température -> index couleur (0-255)
                val = filtered_frame[i]
                idx = int(map_value(val, dynamic_min, dynamic_max, 0, 255))
                idx = max(0, min(255, idx))
                
                sensor_surface.set_at((x, y), COLORS[idx])
                
        except Exception as e:
            # On ignore l'erreur et on passe à la frame suivante
            pass

    # --- RENDU ---
    # Interpolation (Lissage visuel)
    # 1. On agrandit un peu avec 'scale' (rapide et brut)
    #temp_surface = pygame.transform.scale(sensor_surface, (WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
    # 2. On finit l'agrandissement avec 'smoothscale' pour fusionner les pixels
    scaled = pygame.transform.smoothscale(sensor_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
    #scaled = pygame.transform.scale(sensor_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
    screen.blit(scaled, (0, 0))

    # Barre latérale
    pygame.draw.rect(screen, (30, 30, 30), (WINDOW_WIDTH, 0, 100, WINDOW_HEIGHT))
    
    # Échelle de couleurs
    bar_x, bar_h = WINDOW_WIDTH + 35, WINDOW_HEIGHT - 80
    for i in range(256):
        y_pos = WINDOW_HEIGHT - 40 - (i * bar_h / 255)
        pygame.draw.line(screen, COLORS[i], (bar_x, y_pos), (bar_x + 20, y_pos))

    # Affichage des températures
    screen.blit(font.render(f"{dynamic_max:.1f}", True, (255,255,255)), (bar_x - 5, 20))
    screen.blit(font.render(f"{dynamic_min:.1f}", True, (255,255,255)), (bar_x - 5, WINDOW_HEIGHT - 30))
    
    # Stats réelles
    txt_max = font.render(f"MAX: {rmax:.1f}", True, (255,100,100))
    txt_min = font.render(f"MIN: {rmin:.1f}", True, (100,100,255))
    screen.blit(txt_max, (WINDOW_WIDTH + 10, WINDOW_HEIGHT // 2 - 15))
    screen.blit(txt_min, (WINDOW_WIDTH + 10, WINDOW_HEIGHT // 2 + 15))

    pygame.display.flip()
    time.sleep(0.001)

pygame.quit()