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
aguardando_pergunta = False
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
            falando = False

    threading.Thread(target=_falar, daemon=True).start()

# =========================
# IA (OLLAMA)
# =========================
def perguntar_ia(pergunta):
    try:
        print("Perguntando IA:", pergunta)
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
        print("Resposta crua da IA:", resposta)
        # Tentar extrair conteúdo de várias formas possíveis
        # 1) objeto com atributo `message` (SDK Ollama)
        if hasattr(resposta, "message"):
            msg = getattr(resposta, "message")
            if hasattr(msg, "content"):
                return getattr(msg, "content")
            if isinstance(msg, dict) and "content" in msg:
                return msg["content"]

        # 2) dicionário com chave message/content
        if isinstance(resposta, dict):
            if "message" in resposta and isinstance(resposta["message"], dict) and "content" in resposta["message"]:
                return resposta["message"]["content"]
            if "content" in resposta:
                return resposta["content"]

        # 3) objeto/struct com `content` direto
        if hasattr(resposta, "content"):
            return getattr(resposta, "content")

        # fallback: string
        return str(resposta)
    except Exception as e:
        print("Erro ao chamar IA:", repr(e))
        return "Deu erro ao falar com a IA."

def processar_pergunta(pergunta):
    print("Processando pergunta:", pergunta)
    resposta = perguntar_ia(pergunta)
    print("Resposta final para falar:", resposta)
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
    global aguardando_pergunta
    print("🎙️ Atlas iniciado. Fale 'ativar' para ativar.")

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

                # Evita eco e descarta áudio enquanto Atlas fala
                if falando:
                    limpar_fila_audio()
                    continue

                if aguardando_pergunta:
                    print("Você:", texto)
                    aguardando_pergunta = False
                    threading.Thread(
                        target=processar_pergunta,
                        args=(texto,),
                        daemon=True
                    ).start()
                    continue

                print("Você:", texto)

                # Wake word
                if "ativar" in texto or "atlas" in texto:
                    pergunta = texto
                    pergunta = pergunta.replace("ativar", "")
                    pergunta = pergunta.replace("atlas", "").strip()

                    if not pergunta:
                        aguardando_pergunta = True
                        falar("Sim?")
                        continue

                    threading.Thread(
                        target=processar_pergunta,
                        args=(pergunta,),
                        daemon=True
                    ).start()
                else:
                    pergunta = texto
                    threading.Thread(
                        target=processar_pergunta,
                        args=(pergunta,),
                        daemon=True
                    ).start()


# =========================
# START
# =========================
iniciar_assistente()
