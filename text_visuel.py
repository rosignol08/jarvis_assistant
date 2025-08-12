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

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.speaking = False
        self.pulse = 0
        self.base_radius = 0.7
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateAnimation)
        self.timer.start(16)  # ~60 FPS
        
        # Nouvelles variables pour les effets
        self.wave_offset = 0
        self.glow_intensity = 0.5
        self.particle_positions = []
        self.init_particles()

    def init_particles(self):
        # Initialiser des particules flottantes
        for i in range(20):
            angle = (2 * np.pi * i) / 20
            self.particle_positions.append({
                'angle': angle,
                'radius': 0.9 + np.random.random() * 0.3,
                'speed': 0.01 + np.random.random() * 0.02,
                'size': 0.01 + np.random.random() * 0.02
            })

    def updateAnimation(self):
        self.angle += 0.8  # Rotation plus fluide
        self.pulse += 0.12
        self.wave_offset += 0.1
        
        # Mise à jour des particules
        for particle in self.particle_positions:
            particle['angle'] += particle['speed']
            particle['radius'] += 0.001 * math.sin(self.pulse + particle['angle'])
            
        self.update()

    def setSpeaking(self, speaking):
        self.speaking = speaking
        if speaking:
            self.glow_intensity = 1.0
        else:
            self.glow_intensity = 0.5

    def initializeGL(self):
        glClearColor(0.02, 0.02, 0.08, 1)  # Fond plus sombre
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_LINE_SMOOTH)
        glEnable(GL_POINT_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glHint(GL_POINT_SMOOTH_HINT, GL_NICEST)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Effet de glow en arrière-plan
        self.drawGlowBackground()
        
        # Rotation principale
        glPushMatrix()
        glRotatef(self.angle, 0, 0, 1)
        
        # Cercles avec épaisseur et dégradé
        self.drawThickCircleRibbon()
        
        # Cercle intérieur avec effet néon
        self.drawNeonInnerCircle()
        
        glPopMatrix()
        
        # Particules flottantes
        self.drawParticles()
        
        # Ondes de choc quand ça parle
        if self.speaking:
            self.drawSpeechWaves()

    def drawGlowBackground(self):
        # Effet de glow radial
        glPointSize(200)
        glBegin(GL_POINTS)
        intensity = self.glow_intensity * (0.8 + 0.2 * math.sin(self.pulse * 2))
        glColor4f(0.1 * intensity, 0.3 * intensity, 0.6 * intensity, 0.1)
        glVertex2f(0, 0)
        glEnd()

    def drawThickCircleRibbon(self):
        num_segments = 180
        
        # Cercle principal avec épaisseur
        for layer in range(8):  # Plusieurs couches pour l'épaisseur
            layer_offset = layer * 0.008
            glLineWidth(4 - layer * 0.3)
            
            glBegin(GL_LINE_LOOP)
            for i in range(num_segments):
                angle = 2.0 * np.pi * i / num_segments
                
                # Déformation basée sur la parole
                deformation = 1.0
                if self.speaking:
                    deformation = 1.0 + 0.12 * math.sin(self.pulse * 3 + angle * 2)
                    deformation += 0.08 * math.sin(self.pulse * 5 + angle * 4)
                
                radius = (self.base_radius + layer_offset) * deformation
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                # Couleur dégradée avec effet arc-en-ciel
                hue_shift = angle / (2 * np.pi) + self.pulse * 0.1
                r = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(hue_shift * 2))
                g = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(hue_shift * 2 + 2))
                b = 0.9 + 0.1 * (0.5 + 0.5 * math.sin(hue_shift * 2 + 4))
                
                alpha = (1.0 - layer * 0.12) * self.glow_intensity
                glColor4f(r, g, b, alpha)
                glVertex2f(x, y)
            glEnd()

    def drawNeonInnerCircle(self):
        num_segments = 120
        
        # Effet néon avec plusieurs passes
        for pass_num in range(3):
            glLineWidth(8 - pass_num * 2)
            
            glBegin(GL_LINE_LOOP)
            for i in range(num_segments):
                angle = 2.0 * np.pi * i / num_segments
                
                # Effet de pulsation
                pulse_effect = 1.0
                if self.speaking:
                    pulse_effect = 1.0 + 0.3 * math.sin(self.pulse * 6 + angle * 3)
                
                radius = 0.35 * pulse_effect
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                # Couleur néon cyan/blanc
                intensity = 1.0 - pass_num * 0.3
                if pass_num == 0:  # Cœur blanc
                    glColor4f(1.0, 1.0, 1.0, intensity * 0.9)
                else:  # Halo cyan
                    glColor4f(0.3, 0.9, 1.0, intensity * 0.6)
                    
                glVertex2f(x, y)
            glEnd()

    def drawParticles(self):
        glPointSize(4)
        glBegin(GL_POINTS)
        
        for particle in self.particle_positions:
            x = particle['radius'] * math.cos(particle['angle'])
            y = particle['radius'] * math.sin(particle['angle'])
            
            # Couleur scintillante
            twinkle = 0.3 + 0.7 * math.sin(self.pulse * 3 + particle['angle'])
            glColor4f(0.8, 0.9, 1.0, twinkle * 0.8)
            glVertex2f(x, y)
            
        glEnd()

    def drawSpeechWaves(self):
        # Ondes concentriques quand l'IA parle
        for wave in range(3):
            wave_radius = 0.8 + wave * 0.3 + (self.wave_offset % 1.0) * 0.5
            
            glLineWidth(3 - wave)
            glBegin(GL_LINE_LOOP)
            
            for i in range(80):
                angle = 2.0 * np.pi * i / 80
                
                # Déformation de l'onde
                deformation = 1.0 + 0.1 * math.sin(angle * 4 + self.pulse * 2)
                
                radius = wave_radius * deformation
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                
                # Fade out avec la distance
                alpha = 0.6 * (1.0 - (wave_radius - 0.8) / 1.5)
                glColor4f(0.4, 0.8, 1.0, alpha)
                glVertex2f(x, y)
                
            glEnd()

    def resizeGL(self, width, height):
        if height == 0:
            height = 1
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = width / height
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
    '''
    
    def run(self):
        #response: ChatResponse = chat(model=self.model, messages=["salut ça va ?"])
        
        try:
            r = requests.post("http://localhost:11434/api/generate", 
                            json={
                                "model": self.model,
                                "prompt": self.prompt,
                                "stream": False
                            }, 
                            timeout=30)  # Timeout de 30 secondes
            
            if r.status_code != 200:
                self.error_occurred.emit(f"[Erreur HTTP {r.status_code}]")
                return
            
            response_data = r.json()
            
            # Essayer différents champs de réponse
            if 'response' in response_data:
                self.response_received.emit(response_data['response'])
            elif 'content' in response_data:
                self.response_received.emit(response_data['content'])
            elif 'message' in response_data:
                self.response_received.emit(response_data['message'])
            elif 'text' in response_data:
                self.response_received.emit(response_data['text'])
            else:
                available_keys = list(response_data.keys())
                self.error_occurred.emit(f"[Réponse inattendue. Champs disponibles: {available_keys}]")
                
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("[Erreur: Impossible de se connecter à Ollama. Vérifiez que le service est démarré.]")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("[Erreur: Timeout de la requête (30s)]")
        except ValueError as e:
            self.error_occurred.emit(f"[Erreur JSON: {e}]")
        except Exception as e:
            self.error_occurred.emit(f"[Erreur: {e}]")
    '''    

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
    '''
    def test_ollama_connection(self):
        """Tester la connexion à Ollama, afficher les modèles dans la console et choisir le modèle automatiquement"""
        try:
            test_response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if test_response.status_code == 200:
                models_data = test_response.json()
                print("[Ollama] Modèles disponibles:", models_data)
                models = models_data.get('models', [])
                # Recherche du modèle par nom exact
                model_name = None
                for m in models:
                    if m.get('name') == "fotiecodes/jarvis:3b":
                        model_name = m.get('name')
                        break
                if model_name:
                    self.selected_model = model_name
                else:
                    self.selected_model = None
                    self.textEdit.append("<b style='color: #ff0000;'>Erreur:</b> Le modèle 'fotiecodes/jarvis:3b' n'est pas disponible sur Ollama.")
                    self.textEdit.append("<b style='color: #ffaa00;'>Solution:</b> Téléchargez-le avec <code>ollama pull fotiecodes/jarvis:3b</code> dans un terminal.")
            else:
                print(f"[Ollama] Répond mais avec le code {test_response.status_code}")
                self.selected_model = None
                self.textEdit.append(f"<b style='color: #ff6600;'>Attention:</b> Ollama répond mais avec le code {test_response.status_code}")
        except Exception as e:
            print(f"[Ollama] Erreur de connexion: {e}")
            self.selected_model = None
            self.textEdit.append(f"<b style='color: #ff0000;'>Erreur:</b> Impossible de se connecter à Ollama: {e}")
            self.textEdit.append("<b style='color: #ffaa00;'>Solution:</b> Lancez 'ollama serve' dans un terminal")
    '''
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
    '''
    def query_jarvis(self, prompt):
        try:
            r = requests.post("http://localhost:11434/api/generate", json={
                "model": "jarvis:3b",
                "prompt": prompt,
                "stream": False
            })
            
            # Vérifier le statut de la réponse
            if r.status_code != 200:
                return f"[Erreur HTTP {r.status_code}]"
            
            # Analyser la réponse JSON
            response_data = r.json()
            
            # Essayer différents champs de réponse
            if 'response' in response_data:
                return response_data['response']
            elif 'content' in response_data:
                return response_data['content']
            elif 'message' in response_data:
                return response_data['message']
            elif 'text' in response_data:
                return response_data['text']
            else:
                # Si aucun champ reconnu, afficher la structure de la réponse
                available_keys = list(response_data.keys())
                return f"[Réponse inattendue. Champs disponibles: {available_keys}]"
                
        except requests.exceptions.ConnectionError:
            return "[Erreur: Impossible de se connecter à Ollama. Vérifiez que le service est démarré.]"
        except requests.exceptions.Timeout:
            return "[Erreur: Timeout de la requête]"
        except ValueError as e:
            return f"[Erreur JSON: {e}]"
        except Exception as e:
            return f"[Erreur: {e}]"

    def query_jarvis_async(self, prompt):
        """Lancer la requête Ollama via le package Python officiel"""
        if chat is None:
            self.on_error_occurred("Le package 'ollama' n'est pas installé. Installez-le avec 'pip install ollama'.")
            return
        model = getattr(self, 'selected_model', None)
        if not model:
            self.on_error_occurred("Aucun modèle Ollama sélectionné. Vérifiez la connexion et le téléchargement du modèle.")
            return
        def run_chat():
            try:
                # Format des messages pour ollama.chat
                messages = [
                    {"role": "user", "content": prompt}
                ]
                response: ChatResponse = chat(model=model, messages=messages)
                self.on_response_received(response.message.content)
            except Exception as e:
                self.on_error_occurred(f"Erreur Ollama Python: {e}")
        # Lancer dans un thread pour ne pas bloquer l'UI
        threading.Thread(target=run_chat, daemon=True).start()
    '''
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