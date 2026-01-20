import time
import board
import busio
import pygame
import numpy as np
import adafruit_mlx90640

# =========================================================
# CONFIGURATION
# =========================================================

WIDTH, HEIGHT = 32, 24
PIXELS = WIDTH * HEIGHT

SCALE = 20
WIN_W, WIN_H = WIDTH * SCALE, HEIGHT * SCALE

ALPHA = 0.9  # filtre temporel
dynamic_min = 20.0
dynamic_max = 35.0

# =========================================================
# PYGAME
# =========================================================

pygame.init()
screen = pygame.display.set_mode((WIN_W + 100, WIN_H))
pygame.display.set_caption("MLX90640 - NumPy LUT")
font = pygame.font.SysFont(None, 22)

surface = pygame.Surface((WIDTH, HEIGHT))

# =========================================================
# PALETTE LUT (256 x 3)  uint8
# =========================================================

def generate_palette():
    key_colors = np.array([
        (0,   0,   0),
        (45,  0, 135),
        (147, 0, 149),
        (241, 33, 11),
        (255,126, 0),
        (255,206, 0),
        (255,255,255)
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

PALETTE = generate_palette()   # shape (256,3)

# =========================================================
# MLX90640
# =========================================================

mlx = None
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_8_HZ
    print("MLX90640 prêt.")
except Exception as e:
    print("Erreur capteur :", e)

# =========================================================
# BUFFERS NUMPY
# =========================================================

frame          = np.zeros(PIXELS, dtype=np.float32)
frame2         = np.zeros(PIXELS, dtype=np.float32)
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

    if mlx:
        try:
            mlx.getFrame(frame)
            mlx.getFrame(frame2)

            frame[:] = 0.5 * (frame + frame2)

            rmin = frame.min()
            rmax = frame.max()

            dynamic_min = 0.9 * dynamic_min + 0.1 * rmin
            dynamic_max = 0.9 * dynamic_max + 0.1 * rmax

            if first_run:
                filtered_frame[:] = frame
                first_run = False
            else:
                filtered_frame[:] = (
                    filtered_frame * (1 - ALPHA)
                    + frame * ALPHA
                )

        except Exception:
            pass

    # =====================================================
    # TEMP → INDEX (VECTORISÉ)
    # =====================================================

    idx = ((filtered_frame - dynamic_min)
           * 255.0 / (dynamic_max - dynamic_min + 1e-6))

    idx = np.clip(idx, 0, 255).astype(np.uint8)

    # =====================================================
    # INDEX → RGB (LUT)
    # =====================================================

    rgb = PALETTE[idx]                      # (768, 3)
    rgb = rgb.reshape(HEIGHT, WIDTH, 3)     # (24, 32, 3)
    rgb = np.flip(rgb, axis=1)              # flip horizontal
    rgb = np.transpose(rgb, (1, 0, 2))      # >>> (32, 24, 3)

    pygame.surfarray.blit_array(surface, rgb)


    # =====================================================
    # AFFICHAGE PYGAME
    # =====================================================

    pygame.surfarray.blit_array(surface, rgb)
    scaled = pygame.transform.smoothscale(surface, (WIN_W, WIN_H))
    screen.blit(scaled, (0, 0))

    # Barre palette
    pygame.draw.rect(screen, (30, 30, 30), (WIN_W, 0, 100, WIN_H))
    bar_x, bar_h = WIN_W + 35, WIN_H - 80

    for i in range(256):
        y = WIN_H - 40 - (i * bar_h / 255)
        pygame.draw.line(screen, PALETTE[i], (bar_x, y), (bar_x + 20, y))

    screen.blit(font.render(f"{dynamic_max:.1f}", True, (255,255,255)), (bar_x - 5, 20))
    screen.blit(font.render(f"{dynamic_min:.1f}", True, (255,255,255)), (bar_x - 5, WIN_H - 30))
    txt_max = font.render(f"MAX: {rmax:.1f}", True, (255,100,100))
    txt_min = font.render(f"MIN: {rmin:.1f}", True, (100,100,255))
    screen.blit(txt_max, (bar_x -5 , WIN_H // 2 - 15))
    screen.blit(txt_min, (bar_x -5, WIN_H // 2 + 15))

    pygame.display.flip()
    time.sleep(0.001)

pygame.quit()
