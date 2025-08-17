from PyQt5.QtWidgets import QMainWindow, QApplication, QOpenGLWidget, QVBoxLayout, QWidget, QTextEdit, QLineEdit, QPushButton, QComboBox
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
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        self._model_init = True  # Pour différencier init/choix utilisateur
        
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
        layout.addWidget(self.model_combo)
        layout.addWidget(self.glWidget, 3)
        layout.addWidget(self.textEdit, 2)
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.sendButton)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        
        # Tester la connexion Ollama au démarrage (une seule fois)
        QTimer.singleShot(1000, self.test_ollama_connection)

    def test_ollama_connection(self):
        """Tester la connexion à Ollama, afficher les modèles et remplir le menu déroulant"""
        try:
            test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if test_response.status_code == 200:
                models_data = test_response.json()
                print("[Ollama] Modèles disponibles:", models_data)
                models = models_data.get('models', [])
                self.model_combo.clear()
                found = False
                for m in models:
                    if isinstance(m, dict) and m.get('model'):
                        self.model_combo.addItem(m['model'])
                        if m['model'] == "fotiecodes/jarvis:3b":
                            found = True
                if found:
                    self.selected_model = "fotiecodes/jarvis:3b"
                    idx = self.model_combo.findText("fotiecodes/jarvis:3b")
                    if idx >= 0:
                        self._model_init = True  # On va changer l'index, donc c'est encore l'init
                        self.model_combo.setCurrentIndex(idx)
                elif self.model_combo.count() > 0:
                    self.selected_model = self.model_combo.currentText()
                else:
                    self.selected_model = None
                    self.textEdit.append("<b style='color: #ff0000;'>Erreur:</b> Aucun modèle Ollama n'est disponible.")
            else:
                print(f"[Ollama] Répond mais avec le code {test_response.status_code}")
                self.selected_model = None
                self.textEdit.append(f"<b style='color: #ff6600;'>Attention:</b> Ollama répond mais avec le code {test_response.status_code}")
        except Exception as e:
            print(f"[Ollama] Erreur de connexion: {e}")
            self.selected_model = None
            self.textEdit.append(f"<b style='color: #ff0000;'>Erreur:</b> Impossible de se connecter à Ollama: {e}")
            self.textEdit.append("<b style='color: #ffaa00;'>Solution:</b> Lancez 'ollama serve' dans un terminal")

    def on_model_changed(self, idx):
        if self.model_combo.count() > 0:
            self.selected_model = self.model_combo.currentText()
            # Afficher notification et chargement seulement si ce n'est pas l'init
            if getattr(self, '_model_init', False):
                self._model_init = False
            else:
                self.textEdit.append(f"<b style='color: #ffaa00;'>Modèle sélectionné :</b> {self.selected_model}")
                self.show_loading_dots()
                # Simuler un petit délai de chargement (sinon l'UI reste bloquée si le modèle n'est pas prêt)
                QTimer.singleShot(1200, self.stop_loading_dots)

    def send_message(self):
        prompt = self.lineEdit.text()
        if not prompt.strip():
            return

        self.textEdit.append(f"<b style='color: #00d4ff;'>Vous :</b> {prompt}")
        self.lineEdit.clear()

        # Afficher les points de chargement
        self.show_loading_dots()

        # --- Appel à Jarvis en thread (asynchrone) ---
        self.ollama_thread = OllamaThread(prompt, model=self.selected_model or "fotiecodes/jarvis:3b")
        self.ollama_thread.response_received.connect(self.on_response_received)
        self.ollama_thread.error_occurred.connect(self.on_error_occurred)
        self.ollama_thread.start()

    def on_response_received(self, response):
        self.textEdit.append(f"<b style='color: #00ff88;'>Jarvis :</b> {response}")
        self.speak(response)
        self.stop_loading_dots()  # Arrêter l'animation de chargement

    def on_error_occurred(self, error):
        self.textEdit.append(f"<b style='color: #ff0000;'>Erreur :</b> {error}")
        self.glWidget.setSpeaking(False)
        self.stop_loading_dots()  # Arrêter l'animation de chargement
    
    def query_jarvis(self, prompt):
        """Appelle Ollama directement via l'API Python"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response: ChatResponse = chat(model="fotiecodes/jarvis:3b", messages=messages)
            return response["message"]["content"]
        except Exception as e:
            return f"[Erreur Ollama Python: {e}]"

    def query_jarvis_async(self, prompt):
        """Lancer la requête Ollama via le package Python officiel en streaming"""
        try:
            from ollama import chat
        except ImportError:
            self.on_error_occurred("Le package 'ollama' n'est pas installé. Installez-le avec 'pip install ollama'.")
            return
        model = getattr(self, 'selected_model', None)
        if not model:
            self.on_error_occurred("Aucun modèle Ollama sélectionné. Vérifiez la connexion et le téléchargement du modèle.")
            return
        
        def run_chat_stream():
            try:
                messages = [
                    {"role": "user", "content": prompt}
                ]
                # Affichage progressif
                full_text = ""
                self.textEdit.append(f"<b style='color: #00ff88;'>Jarvis :</b> <span id='streaming'></span>")
                cursor = self.textEdit.textCursor()
                cursor.movePosition(cursor.End)
                self.textEdit.setTextCursor(cursor)
                first_token = True
                for chunk in chat(model=model, messages=messages, stream=True):
                    # chunk.message.content contient le texte généré jusqu'ici
                    new_text = chunk.message.content[len(full_text):]
                    full_text = chunk.message.content
                    if new_text:
                        if first_token:
                            self.stop_loading_dots()
                            first_token = False
                        cursor = self.textEdit.textCursor()
                        cursor.movePosition(cursor.End)
                        cursor.insertText(new_text)
                        self.textEdit.setTextCursor(cursor)
                        self.textEdit.ensureCursorVisible()
                # Lancer la synthèse vocale à la fin
                self.speak(full_text)
                self.sendButton.setEnabled(True)
                self.lineEdit.setEnabled(True)
                self.lineEdit.setFocus()
            except Exception as e:
                self.on_error_occurred(f"Erreur Ollama Python (stream): {e}")
        # Désactiver l'UI pendant la génération
        self.sendButton.setEnabled(False)
        self.lineEdit.setEnabled(False)
        threading.Thread(target=run_chat_stream, daemon=True).start()
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

    def show_loading_dots(self):
        """Affiche et anime les points de chargement dans la zone de texte et change le bouton en 'Chargement...'"""
        #self.loading_dots_count = 0
        #self.loading_dots_timer = QTimer()
        #self.loading_dots_timer.timeout.connect(self.update_loading_dots)
        #self.loading_dots_timer.start(400)
        self.loading_dots_base = self.textEdit.toPlainText()
        #self.textEdit.append("<b style='color: #00ff88;'>Jarvis :</b> <span id='dots'>.</span>")
        self.sendButton.setText("Chargement...")

    def update_loading_dots(self):
        self.loading_dots_count = (self.loading_dots_count + 1) % 4
        dots = '.' * self.loading_dots_count
        # Remplacer la dernière ligne par les nouveaux points
        text = self.textEdit.toPlainText().split('\n')
        if text and text[-1].startswith('Jarvis'):
            text[-1] = f"Jarvis : {dots}"
            self.textEdit.setPlainText('\n'.join(text))
            cursor = self.textEdit.textCursor()
            cursor.movePosition(cursor.End)
            self.textEdit.setTextCursor(cursor)

    def stop_loading_dots(self):
        if hasattr(self, 'loading_dots_timer'):
            self.loading_dots_timer.stop()
            del self.loading_dots_timer
        self.sendButton.setText("Envoyer")
        self.sendButton.setEnabled(True)
        self.lineEdit.setEnabled(True)

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