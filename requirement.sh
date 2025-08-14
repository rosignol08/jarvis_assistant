#!/bin/bash

# Installer les dépendances Python
pip install --break-system-packages PyQt5 PyOpenGL

# Vérification que le binaire d'Ollama fonctionne
if command -v ollama &> /dev/null && ollama --version &> /dev/null; then
    echo "Ollama is already installed and working. Skipping installation."
else
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Télécharger le modèle si pas déjà présent
if ! ollama list | grep -q "fotiecodes/jarvis:3b"; then
    echo "Pulling fotiecodes/jarvis:3b model..."
    ollama pull fotiecodes/jarvis:3b
else
    echo "Model fotiecodes/jarvis:3b is already present."
fi

#check les pip
pip install --break-system-packages PyQt5 PyOpenGL numpy requests ollama
echo "Setup completed successfully!"

#sudo apt install espeak espeak-data