@echo off
setlocal enabledelayedexpansion

:: Installer les dépendances Python
echo Installing Python dependencies...
pip install PyQt5 PyOpenGL numpy requests ollama
:: Vérification que le binaire d'Ollama fonctionne
where ollama >nul 2>&1
if %ERRORLEVEL% equ 0 (
    ollama --version >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo Ollama is already installed and working. Skipping installation.
    ) else (
        echo install ollama depuis ce lien https://ollama.com/download/windows
        ::goto :install_ollama
    )
) else (
    ::install_ollama
    ::echo Installing Ollama...
    ::powershell -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/ollama-windows-amd64.zip' -OutFile '%TEMP%\ollama.zip'"
    ::powershell -Command "Expand-Archive -Path '%TEMP%\ollama.zip' -DestinationPath '%USERPROFILE%\ollama' -Force"
    ::setx PATH "%PATH%;%USERPROFILE%\ollama"
    ::set "PATH=%PATH%;%USERPROFILE%\ollama"
)

:: Télécharger le modèle si pas déjà présent
ollama list | findstr "fotiecodes/jarvis:3b" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Pulling fotiecodes/jarvis:3b model...
    ollama pull fotiecodes/jarvis:3b
) else (
    echo Model fotiecodes/jarvis:3b is already present.
)

echo Setup completed successfully!

:: Note: Windows equivalent of espeak would be installing a text-to-speech engine
:: You may use the built-in Windows TTS or download a third-party tool