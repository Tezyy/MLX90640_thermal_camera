#!/bin/bash
set -e

# 1. Mise à jour du système
echo "--- Mise à jour du système ---"
sudo apt-get update && sudo apt-get -y upgrade
sudo apt install --upgrade python3-setuptools -y


# 2. Installation de Python3 et venv s'ils ne sont pas présents
echo "--- Installation de Python et des outils de base ---"
sudo apt-get install -y python3 python3-pip python3-venv

# 3. Création de l'environnement virtuel
echo "--- 2. Création de l'environnement virtuel (mon_env) ---"
if [ ! -d "mon_env" ]; then
    python3 -m venv mon_env
fi

# 4. Activation et installation des bibliothèques
echo "--- Installation de Blinka et des dépendances ---"
source mon_env/bin/activate
pip3 install --upgrade adafruit-python-shell
pip install --upgrade pip
wget https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/raspi-blinka.py
sudo -E env PATH=$PATH python3 raspi-blinka.py

pip3 install adafruit-circuitpython-mlx90640
pip3 install numpy pygame matplotlib scipy cmapy

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

cat <<EOF > camera.py


EOF

cat <<EOF > code.py


EOF

# 6. Fin de l'installation
echo "--- Installation terminée ! ---"
echo "Pour commencer, tapez : source mon_env/bin/activate"
