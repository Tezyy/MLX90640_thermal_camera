# Setup Instructions

1) Ouvrir la Raspberry
2) Copier le fichier setup.sh
3) changer le nom de l'environnement virtuel : variable VENV_NAME
4) sudo setup.sh
5) Attendre le reboot
6) source nom_env_virtuelle/bin/activate
7) Changer potentiellement le T_a et le emissivity dans le fichier adafruitmlx90640_librairie.py
    - trouver le chemin d'accès de la librairie :
    python3 -c "import adafruit_mlx90640; print(adafruit_mlx90640.__file__)"
    - ouvrir avec :
    sudo nano "chemind_accès"
7) Python3 monitoring.py ou python3 image.py

Pour l'aluminium, l'emissivity factor est compris entre 0.2 et 0.7. Donc à tester sur les batteries.
Pour le T_a (ambient temperature), il faut le fixer à une valeur moyenne de température dans la zone de stockage