Voici un exemple simple en PyQt5 + OpenGL (core profile, version 3.3) avec :

des shaders (vertex + fragment),

un VBO avec des points sur une sphère,

et une animation de rotation dans le vertex shader.

📦 Pré-requis
Assure-toi d’avoir ceci installé :

bash
```
pip install PyQt5 PyOpenGL numpy
```
🧪 Exemple avec shaders (OpenGL 3.3 core)

```python
import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QOpenGLWidget, QMainWindow
from PyQt5.QtCore import QTimer
from OpenGL.GL import *
from OpenGL.GL.shaders import compileShader, compileProgram

vertex_shader_source = """
#version 330 core
layout(location = 0) in vec3 position;
uniform float time;
uniform mat4 mvp;

void main() {
    float angle = time;
    mat4 rotY = mat4(
        cos(angle), 0, sin(angle), 0,
        0, 1, 0, 0,
        -sin(angle), 0, cos(angle), 0,
        0, 0, 0, 1
    );
    gl_Position = mvp * rotY * vec4(position, 1.0);
    gl_PointSize = 4.0;
}
"""

fragment_shader_source = """
#version 330 core
out vec4 fragColor;
void main() {
    fragColor = vec4(0.4, 0.8, 1.0, 1.0);
}
"""

def create_sphere_points(lat=20, lon=40):
    points = []
    for i in range(lat):
        theta = np.pi * i / (lat - 1)
        for j in range(lon):
            phi = 2 * np.pi * j / lon
            x = np.sin(theta) * np.cos(phi)
            y = np.cos(theta)
            z = np.sin(theta) * np.sin(phi)
            points.append((x, y, z))
    return np.array(points, dtype=np.float32)

class GLWidget(QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateScene)
        self.timer.start(16)
        self.time = 0.0

    def initializeGL(self):
        self.program = compileProgram(
            compileShader(vertex_shader_source, GL_VERTEX_SHADER),
            compileShader(fragment_shader_source, GL_FRAGMENT_SHADER)
        )

        self.sphere = create_sphere_points()
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.sphere.nbytes, self.sphere, GL_STATIC_DRAW)

        self.mvp_location = glGetUniformLocation(self.program, "mvp")
        self.time_location = glGetUniformLocation(self.program, "time")

        glEnable(GL_PROGRAM_POINT_SIZE)
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)

    def paintGL(self):
        self.time += 0.01
        glClearColor(0, 0, 0, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glUseProgram(self.program)

        projection = np.identity(4, dtype=np.float32)
        projection[3, 2] = -2.5  # recule la caméra

        glUniformMatrix4fv(self.mvp_location, 1, GL_TRUE, projection)
        glUniform1f(self.time_location, self.time)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)

        glDrawArrays(GL_POINTS, 0, len(self.sphere))

        glDisableVertexAttribArray(0)
        glUseProgram(0)

    def updateScene(self):
        self.update()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sphère de particules - Shader")
        self.setCentralWidget(GLWidget())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
```
## 🧠 À toi de modifier ensuite :
Dans le shader vertex :

anime les particules avec du bruit (sin(time + pos.x), etc),

fais-les pulser (gl_PointSize = 2.0 + sin(time + position.x * 10.0) * 1.0),

colore-les dynamiquement en passant la position au fragment shader (via un out vec3 vPos),

fais-les se déplacer autour d’un centre, ou vibrer.


pip install pyttsx3

