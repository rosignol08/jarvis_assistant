import pyttsx3

engine = pyttsx3.init()

# Lister les voix installées
voices = engine.getProperty('voices')
for v in voices:
    print(v.id)

# Choisir une voix française (tu dois avoir une installée sur ton système !)
# Exemple pour Windows : 'HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\SPEECH\Voices\Tokens\TTS_MS_FR-FR_Hortense_11.0'
for voice in voices:
    #if 'fr' in voice.id.lower():
    if 'French (France)' in voice.id:
        print("voix trouvee", voice.id)
        engine.setProperty('voice', 'English (America)')#'French (France)')#voice.id)
        break
engine.setProperty('rate', 130)
engine.say("hello master")
engine.runAndWait()
engine.say("I'm jarvis")
engine.runAndWait()
#engine.say("hallo wie gehts dir ?")
#engine.say("heyy bro ça dit quoi bonjour maitre, je suis Jarvis. comment ça va")
#while(1):


#import pyttsx3
#
## Initialize the Speech Engine
#engine = pyttsx3.init()
#
## Set the language to English (french voices might not work)
#engine.setProperty('voice', 'english')
#
## Text that you want your program to read
#text = "Bonjour, je suis Jarvis."
#
## Speak the text
#engine.say(text)
#
## Wait for the speech to finish before exiting
#engine.runAndWait()