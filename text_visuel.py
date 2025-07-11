from PyQt5.QtWidgets import QMainWindow, QApplication, QOpenGLWidget, QVBoxLayout, QWidget, QTextEdit, QLineEdit, QPushButton
from PyQt5.QtCore import QTimer
from OpenGL.GL import *
import sys
import numpy as np
import requests
import pyttsx3
import math
import os; os.environ['QT_QPA_PLATFORM'] = 'wayland'

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateAnimation)
        self.timer.start(16)  # ~60 FPS

    def updateAnimation(self):
        self.angle += 0.5
        self.update()

    def initializeGL(self):
        glClearColor(0, 0, 0, 1)
        glEnable(GL_POINT_SMOOTH)
        glPointSize(3)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(self.angle, 0, 0, 1)

        glBegin(GL_POINTS)
        for theta in np.linspace(0, np.pi/2, 50): # Limiting theta to pi/2 will make it more circular.
            for phi in np.linspace(0, 2*np.pi, 60):
                x = np.sin(theta) * np.cos(phi)
                y = np.sin(theta) * np.sin(phi)
                z = 0#np.cos(theta)
                glColor3f(0.5 + 0.5*z, 0.5 + 0.5*y, 1.0)
                glVertex3f(x, y, z)
        #for theta in np.linspace(0, np.pi, 30):
        #    for phi in np.linspace(0, 2*np.pi, 60):
        #        
        #        #x = np.sin(theta) * np.cos(phi)
        #        #y = np.sin(theta) * np.sin(phi)
        #        #z = np.cos(theta)
        #        #glColor3f(0.5 + 0.5*z, 0.5 + 0.5*y, 1.0)
        #        #glVertex3f(x, y, z)
        glEnd()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis Assistant")

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

    def send_message(self):
        prompt = self.lineEdit.text()
        if not prompt.strip():
            return

        self.textEdit.append(f"<b>Vous :</b> {prompt}")
        self.lineEdit.clear()

        # --- Appel à Jarvis ---
        response = self.query_jarvis(prompt)
        self.textEdit.append(f"<b>Jarvis :</b> {response}")
        self.speak(response)

    def query_jarvis(self, prompt):
        try:
            r = requests.post("http://localhost:11434/api/generate", json={
                "model": "jarvis:3b",
                "prompt": prompt,
                "stream": False
            })
            return r.json()["response"]
        except Exception as e:
            return f"[Erreur: {e}]"

    def speak(self, text):
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())