import queue
import json
import sounddevice as sd
import pyttsx3
import ollama
import threading

from vosk import Model, KaldiRecognizer

# =========================
# VOZ
# =========================

engine = pyttsx3.init()

falando = False
ativo = False

voices = engine.getProperty('voices')

# muda voz (teste índices diferentes)
engine.setProperty('voice', voices[0].id)

# velocidade
engine.setProperty('rate', 175)


def limpar_fila_audio():

    while not q.empty():
        q.get()

def falar_thread(texto):

    global falando

    falando = True

    print("Atlas:", texto)

    engine.say(texto)
    engine.runAndWait()

    limpar_fila_audio()

    falando = False

def falar(texto):

    global falando

    if falando:
        return

    t = threading.Thread(
        target=falar_thread,
        args=(texto,)
    )

    t.daemon = True
    t.start()

# =========================
# IA
# =========================

def perguntar_ia(pergunta):
    print("Pergunta enviada:", pergunta)   
    resposta = ollama.chat(
        model='llama3',
        messages=[
            {
                'role': 'system',
                'content': '''
Você é Atlas.

Um assistente inteligente, amigável e descontraído.
Responda sempre de forma curta e natural.
'''
            },
            {
                'role': 'user',
                'content': pergunta
            }
        ]
    )
    resposta_texto = resposta['message']['content']

    print("Resposta IA:", resposta_texto)
    return resposta['message']['content']

# =========================
# VOSK
# =========================

model = Model("vosk-model-small-pt-0.3")
recognizer = KaldiRecognizer(model, 16000)

q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

# =========================
# MICROFONE
# =========================

with sd.RawInputStream(
    samplerate=16000,
    blocksize=8000,
    dtype='int16',
    channels=1,
    callback=callback
):

    print("Atlas ouvindo...")

    while True:

        data = q.get()

        if recognizer.AcceptWaveform(data):

            resultado = json.loads(recognizer.Result())

            texto = resultado.get("text", "").lower().strip()

            if texto == "":
                continue

            print("Você:", texto)

            # evita ouvir a própria voz
            if falando:
                continue

            # ativação
            if "atlas" in texto:

                pergunta = texto.replace("atlas", "").strip()

                if pergunta == "":
                    falar("Sim?")
                    continue

                resposta = perguntar_ia(pergunta)
                print("Atlas:", resposta)
                falar(resposta)