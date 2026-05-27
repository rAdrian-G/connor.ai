import queue
import json
import sounddevice as sd
import pyttsx3
import ollama
import threading
from vosk import Model, KaldiRecognizer

# =========================
# CONFIG GERAL
# =========================
q = queue.Queue()
falando = False
lock_fala = threading.Lock()

# =========================
# VOZ (TTS)
# =========================
engine = pyttsx3.init()

voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)
engine.setProperty('rate', 175)

def limpar_fila_audio():
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass

def falar(texto):
    def _falar():
        global falando
        with lock_fala:
            falando = True
            print("Atlas:", texto)
            engine.say(texto)
            engine.runAndWait()
            limpar_fila_audio()
            falando = False

    threading.Thread(target=_falar, daemon=True).start()

# =========================
# IA (OLLAMA)
# =========================
def perguntar_ia(pergunta):
    try:
        resposta = ollama.chat(
            model="llama3",
            messages=[
                {
                    "role": "system",
                    "content": "Você é Atlas, um assistente rápido, amigável e direto. Responda curto."
                },
                {
                    "role": "user",
                    "content": pergunta
                }
            ]
        )
        return resposta["message"]["content"]
    except Exception as e:
        return "Deu erro ao falar com a IA."

def processar_pergunta(pergunta):
    resposta = perguntar_ia(pergunta)
    falar(resposta)

# =========================
# VOSK (STT)
# =========================
model = Model("vosk-model-small-pt-0.3")
recognizer = KaldiRecognizer(model, 16000)

def callback(indata, frames, time, status):
    q.put(bytes(indata))

# =========================
# LOOP PRINCIPAL
# =========================
def iniciar_assistente():
    print("🎙️ Atlas iniciado. Fale 'Atlas' para ativar.")

    with sd.RawInputStream(
        samplerate=16000,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        while True:
            data = q.get()

            if recognizer.AcceptWaveform(data):
                resultado = json.loads(recognizer.Result())
                texto = resultado.get("text", "").lower().strip()

                if not texto:
                    continue

                # Evita eco
                if falando:
                    continue

                print("Você:", texto)

                # Wake word
                if "atlas" in texto:
                    pergunta = texto.replace("atlas", "").strip()

                    if not pergunta:
                        falar("Sim?")
                        continue

                    # NÃO bloqueia o sistema
                    threading.Thread(
                        target=processar_pergunta,
                        args=(pergunta,),
                        daemon=True
                    ).start()

# =========================
# START
# =========================
iniciar_assistente()
