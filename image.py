import time
import board
import busio
import pygame
import adafruit_mlx90640

# --- CONFIGURATION ---
FIXED_MIN_TEMP = 0.0  
FIXED_MAX_TEMP = 40.0  
WIDTH_CAM, HEIGHT_CAM = 32, 24
WINDOW_SCALE = 20  
WINDOW_WIDTH, WINDOW_HEIGHT = WIDTH_CAM * WINDOW_SCALE, HEIGHT_CAM * WINDOW_SCALE

# Initialisation fenêtre PyGame
print("Démarrage de Pygame...")
pygame.init()
screen = pygame.display.set_mode((WINDOW_WIDTH + 100, WINDOW_HEIGHT))
pygame.display.set_caption("MLX90640 Pro - 0-40°C")
font = pygame.font.SysFont(None, 22)

# Palette (256 couleurs)
COLORS = []
def generate_palette():
    key_colors = [(0,0,0), (45,0,135), (147,0,149), (241,33,11), (255,126,0), (255,206,0), (255,255,255)]
    segments = len(key_colors) - 1
    steps_per_segment = 256 // segments
    for i in range(segments):
        c1, c2 = key_colors[i], key_colors[i+1]
        for step in range(steps_per_segment):
            r = int(c1[0] + (c2[0] - c1[0]) * step / steps_per_segment)
            g = int(c1[1] + (c2[1] - c1[1]) * step / steps_per_segment)
            b = int(c1[2] + (c2[2] - c1[2]) * step / steps_per_segment)
            COLORS.append((r, g, b))
    while len(COLORS) < 256: COLORS.append((255, 255, 255))
generate_palette()

# Initialisation mlx90640
mlx = None
try:
    # la fréquence de l'i2c n'est pas programmable dans python il faut aller la
    # changer dans le kernel linux. 
    #i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
    i2c = busio.I2C(board.SCL, board.SDA) 
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
    print("Capteur MLX90640 détecté et prêt.")
except Exception as e:
    print(f"ATTENTION : Le capteur n'a pas pu démarrer ({e})")
    print("La fenêtre va s'ouvrir en mode simulation (écran noir).")

# Variables de travail
sensor_surface = pygame.Surface((WIDTH_CAM, HEIGHT_CAM))
frame = [0.0] * 768
filtered_frame = [0.0] * 768
ALPHA = 0.5 

def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

# --- BOUCLE PRINCIPALE ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if mlx is not None:
        try:
            mlx.getFrame(frame)
            rmin, rmax = min(frame), max(frame)
            for i in range(768):
                filtered_frame[i] = (filtered_frame[i] * (1 - ALPHA)) + (frame[i] * ALPHA)
                x, y = i % 32, i // 32
                color_idx = int(map_value(filtered_frame[i], FIXED_MIN_TEMP, FIXED_MAX_TEMP, 0, 255))
                color_idx = max(0, min(255, color_idx))
                sensor_surface.set_at((x, y), COLORS[color_idx])
        except Exception as e:
            print(f"Erreur lecture frame: {e}")

    scaled_surface = pygame.transform.smoothscale(sensor_surface, (WINDOW_WIDTH, WINDOW_HEIGHT))
    screen.blit(scaled_surface, (0, 0))

    # Légende
    pygame.draw.rect(screen, (20, 20, 20), (WINDOW_WIDTH, 0, 100, WINDOW_HEIGHT))
    bar_x, bar_h = WINDOW_WIDTH + 30, WINDOW_HEIGHT - 80
    for i in range(256):
        y_pos = WINDOW_HEIGHT - 40 - (i * bar_h / 255)
        pygame.draw.line(screen, COLORS[i], (bar_x, y_pos), (bar_x + 20, y_pos))

    screen.blit(font.render(f"{FIXED_MAX_TEMP}C", True, (255,255,255)), (bar_x, 20))
    screen.blit(font.render(f"{FIXED_MIN_TEMP}C", True, (255,255,255)), (bar_x, WINDOW_HEIGHT - 30))
    
    if mlx:
        screen.blit(font.render(f"Max: {rmax:.1f}", True, (255,255,255)), (WINDOW_WIDTH + 10, WINDOW_HEIGHT//2))
        screen.blit(font.render(f"Min: {rmin:.1f}", True, (255,255,255)), (WINDOW_WIDTH + 10, WINDOW_HEIGHT//2 +20)) #+ 20 car l'image est flip à la fin

        

    pygame.display.flip()
    time.sleep(0.001)

pygame.quit()