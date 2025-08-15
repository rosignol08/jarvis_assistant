from PyQt5.QtWidgets import QMainWindow, QApplication, QOpenGLWidget, QVBoxLayout, QWidget, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from OpenGL.GL import *
import sys
import numpy as np
import requests
import math
import threading
import subprocess

# Supprimer complètement les warnings Qt
import os
os.environ['QT_LOGGING_RULES'] = '*=false'
os.environ['QT_ASSUME_STDERR_HAS_CONSOLE'] = '1'

# Gestion Wayland propre
if os.environ.get('XDG_SESSION_TYPE') == 'wayland' or 'WAYLAND_DISPLAY' in os.environ:
    os.environ['QT_QPA_PLATFORM'] = 'wayland'

try:
    from ollama import chat
    from ollama import ChatResponse
    from ollama import list as ollama_list
except ImportError:
    chat = None
    ChatResponse = None

class TTSManager:
    """Gestionnaire TTS utilisant espeak directement pour éviter les conflits Qt"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def speak_text(self, text):
        """Utiliser espeak directement via subprocess pour éviter les conflits"""
        import subprocess
        import shlex
        
        def speak_in_thread():
            try:
                # Utiliser espeak directement (plus fiable que pyttsx3)
                text_clean = text.replace('"', '\\"')
                cmd = f'espeak -s 150 -v fr "{text_clean}"'
                subprocess.run(cmd, shell=True, capture_output=True)
            except Exception as e:
                try:
                    # Fallback vers festival si espeak n'est pas disponible
                    text_clean = text.replace("'", "\\'")
                    subprocess.run(f"echo '{text_clean}' | festival --tts", 
                                 shell=True, capture_output=True)
                except:
                    try:
                        # Dernier fallback vers pyttsx3 mais dans un processus séparé
                        import multiprocessing
                        def pyttsx3_process(text):
                            import pyttsx3
                            engine = pyttsx3.init()
                            engine.say(text)
                            engine.runAndWait()
                        
                        p = multiprocessing.Process(target=pyttsx3_process, args=(text,))
                        p.start()
                        p.join(timeout=10)  # Max 10 secondes
                        if p.is_alive():
                            p.terminate()
                    except:
                        print(f"TTS indisponible: {e}")
        
        # Lancer dans un thread Python standard (pas Qt)
        import threading
        thread = threading.Thread(target=speak_in_thread, daemon=True)
        thread.start()
        return thread

import math
import random
import numpy as np
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import QTimer
from OpenGL.GL import *

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.speaking = False  # <- état parole
        
        self.num_points = 80
        self.circles = [
            self.init_circle(0.35),  # Petit cercle
            self.init_circle(0.65)   # Grand cercle
        ]
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateAnimation)
        self.timer.start(16)  # ~60 FPS

    def setSpeaking(self, speaking):
        """Définit si l'IA parle ou non"""
        self.speaking = speaking

    def init_circle(self, base_radius):
        points = []
        for i in range(self.num_points):
            angle = (2 * math.pi * i) / self.num_points
            points.append({
                "angle": angle,
                "base_radius": base_radius,
                "offset": 0.0,
                "target_offset": 0.0,
                "speed": 0.02 + random.random() * 0.03
            })
        return points
    def updateAnimation(self):
        amplitude = 0.8 if self.speaking else 0.08  # plus large quand ça parle
        
        for circle in self.circles:
            for p in circle:
                if random.random() < 0.1:
                    p["target_offset"] = (random.random() - 0.5) * amplitude
                p["offset"] += (p["target_offset"] - p["offset"]) * 0.05
        
        self.update()


    def initializeGL(self):
        glClearColor(0.02, 0.02, 0.05, 1.0)  # Fond sombre
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        glColor4f(1.0, 1.0, 1.0, 0.9)  # Blanc pur
        glLineWidth(1.5)

        for circle in self.circles:
            glBegin(GL_LINE_LOOP)
            for p in circle:
                radius = p["base_radius"] + p["offset"]
                x = radius * math.cos(p["angle"])
                y = radius * math.sin(p["angle"])
                glVertex2f(x, y)
            glEnd()

    def resizeGL(self, width, height):
        if height == 0:
            height = 1
        aspect = width / height
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(-aspect, aspect, -1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)

class OllamaThread(QThread):
    """Thread pour les requêtes Ollama afin d'éviter le blocage de l'interface"""
    response_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, prompt, model="fotiecodes/jarvis:3b"):
        super().__init__()
        self.prompt = prompt
        self.model = model
    
    def run(self):
        """Appelle Ollama avec l'API Python"""
        try:
            messages = [{"role": "user", "content": self.prompt}]
            response: ChatResponse = chat(model=self.model, messages=messages)

            if "message" in response and "content" in response["message"]:
                self.response_received.emit(response["message"]["content"])
            else:
                available_keys = list(response.keys())
                self.error_occurred.emit(f"[Réponse inattendue. Champs disponibles: {available_keys}]")

        except Exception as e:
            self.error_occurred.emit(f"[Erreur Ollama Python: {e}]")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis Assistant - Interface Stylée")
        
        # Initialiser le gestionnaire TTS
        self.tts_manager = TTSManager()
        self.current_speech_thread = None
        self.selected_model = None  # Nouveau attribut pour le modèle sélectionné
        self.ollama_thread = None  # Nouveau attribut pour le thread Ollama
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a2e;
                color: #ffffff;
            }
            QTextEdit {
                background-color: #16213e;
                color: #ffffff;
                border: 2px solid #0f3460;
                border-radius: 10px;
                padding: 10px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
            QLineEdit {
                background-color: #16213e;
                color: #ffffff;
                border: 2px solid #0f3460;
                border-radius: 8px;
                padding: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #00d4ff;
            }
            QPushButton {
                background-color: #0f3460;
                color: #ffffff;
                border: 2px solid #00d4ff;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00d4ff;
                color: #1a1a2e;
            }
            QPushButton:pressed {
                background-color: #0099cc;
            }
        """)

        self.glWidget = GLWidget()
        self.textEdit = QTextEdit()
        self.lineEdit = QLineEdit()
        self.sendButton = QPushButton("Envoyer")

        self.sendButton.clicked.connect(self.send_message)
        self.lineEdit.returnPressed.connect(self.send_message)

        layout = QVBoxLayout()
        layout.addWidget(self.glWidget, 3)
        layout.addWidget(self.textEdit, 2)
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.sendButton)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # Tester la connexion Ollama au démarrage
        QTimer.singleShot(1000, self.test_ollama_connection)

        # Tester la connexion Ollama au démarrage
        self.test_ollama_connection()
    def test_ollama_connection(self):
        """Tester la connexion à Ollama, afficher les modèles et choisir automatiquement"""
        try:
            test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if test_response.status_code == 200:
                models_data = test_response.json()
                print("[Ollama] Modèles disponibles:", models_data)
    
                models = models_data.get('models', [])
                model_name = None
    
                for m in models:
                    # Le nom du modèle est dans la clé "model" et pas "name"
                    if isinstance(m, dict):
                        if m.get('model') == "fotiecodes/jarvis:3b":
                            model_name = m.get('model')
                            break
                        
                if model_name:
                    self.selected_model = model_name
                else:
                    self.selected_model = None
                    self.textEdit.append(
                        "<b style='color: #ff0000;'>Erreur:</b> "
                        "Le modèle 'fotiecodes/jarvis:3b' n'est pas disponible sur Ollama."
                    )
                    self.textEdit.append(
                        "<b style='color: #ffaa00;'>Solution:</b> "
                        "Téléchargez-le avec <code>ollama pull fotiecodes/jarvis:3b</code> dans un terminal."
                    )
            else:
                print(f"[Ollama] Répond mais avec le code {test_response.status_code}")
                self.selected_model = None
                self.textEdit.append(
                    f"<b style='color: #ff6600;'>Attention:</b> "
                    f"Ollama répond mais avec le code {test_response.status_code}"
                )
    
        except Exception as e:
            print(f"[Ollama] Erreur de connexion: {e}")
            self.selected_model = None
            self.textEdit.append(
                f"<b style='color: #ff0000;'>Erreur:</b> Impossible de se connecter à Ollama: {e}"
            )
            self.textEdit.append(
                "<b style='color: #ffaa00;'>Solution:</b> Lancez 'ollama serve' dans un terminal"
            )
 
    def send_message(self):
        prompt = self.lineEdit.text()
        if not prompt.strip():
            return

        self.textEdit.append(f"<b style='color: #00d4ff;'>Vous :</b> {prompt}")
        self.lineEdit.clear()

        # --- Appel à Jarvis ---
        response = self.query_jarvis(prompt)
        self.textEdit.append(f"<b style='color: #00ff88;'>Jarvis :</b> {response}")
        self.speak(response)
    
    def query_jarvis(self, prompt):
        """Appelle Ollama directement via l'API Python"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response: ChatResponse = chat(model="fotiecodes/jarvis:3b", messages=messages)
            return response["message"]["content"]
        except Exception as e:
            return f"[Erreur Ollama Python: {e}]"

    def query_jarvis_async(self, prompt):
        """Version non-bloquante pour PyQt"""
        def run_chat():
            try:
                messages = [{"role": "user", "content": prompt}]
                response: ChatResponse = chat(model="fotiecodes/jarvis:3b", messages=messages)
                self.on_response_received(response["message"]["content"])
            except Exception as e:
                self.on_error_occurred(f"[Erreur Ollama Python: {e}]")

        import threading
        threading.Thread(target=run_chat, daemon=True).start()
    def speak(self, text):
        """Nouvelle méthode TTS robuste"""
        if not text or not text.strip():
            return
            
        # Activer l'animation
        self.glWidget.setSpeaking(True)
        
        # Fonction pour gérer la fin de la parole
        def on_speech_end():
            # Petit délai avant de désactiver l'animation
            QTimer.singleShot(500, lambda: self.glWidget.setSpeaking(False))
        
        try:
            # Lancer la synthèse vocale
            self.current_speech_thread = self.tts_manager.speak_text(text)
            
            # Timer pour détecter la fin (approximative)
            estimated_duration = len(text) * 50  # ~50ms par caractère
            QTimer.singleShot(estimated_duration, on_speech_end)
            
        except Exception as e:
            print(f"Erreur TTS: {e}")
            self.glWidget.setSpeaking(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        window = MainWindow()
        window.resize(900, 700)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)