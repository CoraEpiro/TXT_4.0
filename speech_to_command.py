from __future__ import annotations
import io, json, os, re, time
from typing import List, Dict, Tuple, Optional
import numpy as np
import sounddevice as sd
import soundfile  as sf
import speech_recognition as sr
import paho.mqtt.client as mqtt
from openai import OpenAI
from TTS.api import TTS
from dotenv import load_dotenv
from langdetect import detect, DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException
import whisper

# Set seed for consistent language detection
DetectorFactory.seed = 0

# ═════════════════════════════ CONFIG ═══════════════════════════════════════
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINETUNED_MODEL = os.getenv("FINETUNED_MODEL")
FALLBACK_MODEL = ""

MQTT_BROKER, MQTT_PORT, MQTT_TOPIC = "test.mosquitto.org", 1883, "txt4/action"

# OpenAI-TTS defaults (override in .env)
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")   # or "tts-1-hd"
OPENAI_VOICE     = os.getenv("OPENAI_VOICE", "alloy")       # alloy / onyx …

# Optional loudness match for Coqui vs OpenAI (dB)
COQUI_GAIN_DB = float(os.getenv("COQUI_GAIN_DB", "0"))
# ═════════════════════ INITIALISE CLIENTS ═══════════════════════════════════
openai_client = OpenAI(api_key=OPENAI_API_KEY)

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    print(f"🔌 MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"⚠️ MQTT connection failed: {e}")
    mqtt_client = None

# ═════════════════════ COQUI-TTS SETUP ══════════════════════════════════════
COQUI_MODELS: Dict[str, Tuple[str, Optional[str]]] = {
    "en-US": ("tts_models/en/ljspeech/tacotron2-DDC", None),
    "de-DE": ("tts_models/de/thorsten/tacotron2-DDC", None),
    "tr-TR": ("tts_models/tr/common-voice/glow-tts", None),
    "fr-FR": ("tts_models/fr/css10/vits", None),
    "es-ES": ("tts_models/es/mai/tacotron2-DDC", None),
    "it-IT": ("tts_models/multilingual/multi-dataset/your_tts", "it_0"),
    "ru-RU": ("tts_models/ru/ru_v3", None),
}
MULTI_SPKR_MODEL = "tts_models/multilingual/multi-dataset/your_tts"
SPK_MAP = {"it-IT": "it_0", "fr-FR": "fr_0", "tr-TR": "tr_0",
           "en-US": "en_0", "de-DE": "de_0", "es-ES": "es_0", "ru-RU": "ru_0"}

tts_cache: Dict[str, Tuple[TTS, Optional[str]]] = {}
def get_tts(lang: str) -> Tuple[TTS, Optional[str]]:
    name, dflt = COQUI_MODELS.get(lang, (MULTI_SPKR_MODEL, "en_0"))
    if lang not in tts_cache:
        try:
            tts_cache[lang] = (TTS(name, progress_bar=False, gpu=False), dflt)
        except Exception as e:
            print("⚠️  Coqui load failed, using multilingual model →", e)
            tts_cache[lang] = (TTS(MULTI_SPKR_MODEL, progress_bar=False, gpu=False), "en_0")
    return tts_cache[lang]

# ═════════════════════ SPEAK (OpenAI → Coqui) ═══════════════════════════════
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
def _split(txt: str, max_len: int = 200) -> List[str]:
    out, buf = [], ""
    for part in _SENT_SPLIT.split(txt):
        if len(buf) + len(part) > max_len:
            out.append(buf.strip()); buf = part
        else:
            buf += " " + part
    if buf.strip(): out.append(buf.strip())
    return out

def speak(text: str, lang: str = "en-US") -> None:
    clean = re.sub(r"[`*_#>\"“”]", "", text).strip()
    try:
        t0 = time.time()
        rsp = openai_client.audio.speech.create(
            model  = OPENAI_TTS_MODEL,
            voice  = OPENAI_VOICE,  # e.g., 'alloy', 'onyx', 'nova', etc.
            input  = clean,
        )
        data, sr = sf.read(io.BytesIO(rsp.read()), dtype="float32")
        sd.play(data, sr); sd.wait()
        print(f"[🔊 OPENAI] {time.time()-t0:.2f}s • {len(data)} samples")
        return
    except Exception as err:
        print(f"❌ OpenAI-TTS error: {err}")
        print("[TTS] Could not speak the response.")
        # No fallback to Coqui or any other TTS

# ═════════════════════ LANG / INTENT HELPERS ════════════════════════════════
LANG_MAP = {
    "english": "en-US", "ingilizce": "en-US", "german": "de-DE", "deutsch": "de-DE",
    "almanca": "de-DE", "turkish": "tr-TR", "türkçe": "tr-TR", "french": "fr-FR",
    "français": "fr-FR", "spanish": "es-ES", "español": "es-ES",
    "italian": "it-IT", "italiano": "it-IT",
    # Add more Turkish words for better detection
    "evet": "tr-TR", "hayır": "tr-TR", "tamam": "tr-TR", "anladım": "tr-TR",
    "beni": "tr-TR", "anlayabiliyor": "tr-TR", "musun": "tr-TR", "türkçe": "tr-TR",
    # Russian
    "russian": "ru-RU", "русский": "ru-RU", "русский язык": "ru-RU", "по-русски": "ru-RU"
}

# Language detection mapping for langdetect results
DETECT_LANG_MAP = {
    "en": "en-US",
    "de": "de-DE", 
    "tr": "tr-TR",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "ru": "ru-RU"
}

# Common words for each language to improve detection
LANG_WORDS = {
    "en-US": ["hello", "hi", "hey", "yes", "no", "okay", "good", "bad", "move", "turn", "left", "right", "forward", "back", "the", "and", "you", "me", "what", "how", "why", "when", "where", "who"],
    "tr-TR": ["merhaba", "selam", "evet", "hayır", "tamam", "iyi", "kötü", "hareket", "dön", "sol", "sağ", "ileri", "geri", "beni", "anlayabiliyor", "musun", "sen", "ben", "ne", "nasıl", "neden", "ne zaman", "nerede", "kim", "bu", "şu", "o", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz", "on", "lütfen", "teşekkür", "rica", "güzel", "kötü", "büyük", "küçük", "uzun", "kısa", "yeni", "eski", "genç", "yaşlı"],
    "de-DE": ["hallo", "ja", "nein", "gut", "schlecht", "bewegen", "drehen", "links", "rechts", "vorwärts", "rückwärts", "bitte", "danke", "schön", "schlecht", "groß", "klein", "lang", "kurz", "neu", "alt", "jung", "alt"],
    "fr-FR": ["bonjour", "oui", "non", "bien", "mal", "bouger", "tourner", "gauche", "droite", "avant", "arrière", "s'il vous plaît", "merci", "beau", "mauvais", "grand", "petit", "long", "court", "nouveau", "vieux", "jeune", "vieux"],
    "es-ES": ["hola", "sí", "no", "bueno", "malo", "mover", "girar", "izquierda", "derecha", "adelante", "atrás", "por favor", "gracias", "bonito", "feo", "grande", "pequeño", "largo", "corto", "nuevo", "viejo", "joven", "viejo"],
    "it-IT": ["ciao", "sì", "no", "bene", "male", "muovere", "girare", "sinistra", "destra", "avanti", "indietro", "per favore", "grazie", "bello", "brutto", "grande", "piccolo", "lungo", "corto", "nuovo", "vecchio", "giovane", "vecchio"],
    "ru-RU": [
        "привет", "здравствуйте", "да", "нет", "хорошо", "плохо", "двигаться", "повернуть", "налево", "направо", "вперёд", "назад", "пожалуйста", "спасибо", "большой", "маленький", "длинный", "короткий", "новый", "старый", "молодой", "старый", "робот", "команда", "движение", "выполнить", "стоп", "остановить", "поехали", "команду", "вперёд", "назад", "налево", "направо"
    ]
}

def word_based_language_detection(text: str) -> Optional[str]:
    """Detect language based on common words"""
    text_lower = text.lower()
    scores = {}
    
    for lang, words in LANG_WORDS.items():
        score = sum(1 for word in words if word in text_lower)
        if score > 0:
            scores[lang] = score
    
    if scores:
        # Only return if we have a clear winner (score difference > 1)
        best_lang = max(scores.items(), key=lambda x: x[1])
        second_best = None
        if len(scores) > 1:
            second_best = sorted(scores.items(), key=lambda x: x[1], reverse=True)[1]
        
        # Only detect if we have a clear winner and minimum score
        if best_lang[1] >= 2 and (not second_best or (best_lang[1] - second_best[1]) > 1):
            print(f"🔍 Word-based detection: {best_lang[0]} (score: {best_lang[1]})")
            return best_lang[0]
        else:
            if second_best:
                print(f"🔍 Ambiguous word detection: {best_lang[0]} ({best_lang[1]}) vs {second_best[0]} ({second_best[1]})")
            else:
                print(f"🔍 Low confidence word detection: {best_lang[0]} (score: {best_lang[1]})")
    
    # If no words match, try partial word matching for Turkish
    turkish_chars = ['ç', 'ğ', 'ı', 'ö', 'ş', 'ü']
    if any(char in text_lower for char in turkish_chars):
        print(f"🔍 Turkish detected by special characters")
        return "tr-TR"
    
    return None

def auto_detect_language(text: str) -> Optional[str]:
    """Automatically detect language from text and return language code with confidence check"""
    # First try word-based detection (more reliable for short phrases)
    word_detected = word_based_language_detection(text)
    if word_detected:
        return word_detected
    
    # Fall back to langdetect for longer texts
    try:
        # Get all detected languages with confidence scores
        detected_langs = detect_langs(text)
        if not detected_langs:
            print(f"🔍 No languages detected for: {text}")
            return None
        
        # Get the most confident detection
        best_lang = detected_langs[0]
        print(f"🔍 Detected: {best_lang.lang} (confidence: {best_lang.prob:.3f}) for: {text}")
        
        # Lower confidence threshold to 0.5 for better detection
        if best_lang.prob >= 0.5:
            detected_code = DETECT_LANG_MAP.get(best_lang.lang)
            if detected_code:
                print(f"🔍 Language switch to: {detected_code}")
                return detected_code
        
        return None
    except LangDetectException as e:
        print(f"🔍 Language detection error: {e}")
        return None

# Language switch phrases that should not generate commands
LANGUAGE_SWITCH_PHRASES = [
    "i want to talk in", "i want to speak in", "switch to", "change to", "let's speak",
    "ich möchte sprechen", "ich will sprechen", "wechseln zu", "ändern zu",
    "quiero hablar", "quiero hablar en", "cambiar a", "cambia a",
    "je veux parler", "je veux parler en", "changer à", "change à",
    "voglio parlare", "voglio parlare in", "cambiare a", "cambia a",
    "almanca", "türkçe", "ingilizce", "fransızca", "ispanyolca", "italyanca",
    "german", "turkish", "english", "french", "spanish", "italian",
    # Russian
    "я хочу говорить на", "я хочу говорить по", "переключить на", "сменить на", "давай говорить на", "русский", "по-русски"
]

def detect_explicit_language_request(text: str) -> Optional[str]:
    """Detect explicit language switch requests more accurately"""
    text_lower = text.lower()
    
    # Direct language name detection
    if "german" in text_lower or "deutsch" in text_lower or "almanca" in text_lower:
        return "de-DE"
    elif "english" in text_lower or "ingilizce" in text_lower:
        return "en-US"
    elif "turkish" in text_lower or "türkçe" in text_lower:
        return "tr-TR"
    elif "french" in text_lower or "français" in text_lower or "fransızca" in text_lower:
        return "fr-FR"
    elif "spanish" in text_lower or "español" in text_lower or "ispanyolca" in text_lower:
        return "es-ES"
    elif "italian" in text_lower or "italiano" in text_lower or "italyanca" in text_lower:
        return "it-IT"
    elif "russian" in text_lower or "русский" in text_lower or "по-русски" in text_lower:
        return "ru-RU"
    
    return None

def is_language_switch_request(text: str) -> bool:
    """Check if the user is just requesting a language switch"""
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in LANGUAGE_SWITCH_PHRASES)

CMD_HINTS = ("forward","back","move","spin","turn","left","right","wait",
             "geri","ileri","dön","bekle","links","rechts")
likely_cmd = lambda t:any(w in t.lower() for w in CMD_HINTS)

# ═════════════════════ GPT + JSON PARSER ════════════════════════════════════
SYSTEM_PROMPT = """
You are a robot command parser. Your job is to convert user requests for robot movements into JSON commands.

- Only output JSON, never explanations or conversation.
- Each command must be a JSON object with these keys: M1_dir, M2_dir, speed, step_size.
- For turns: M1_dir and M2_dir must be opposite (\"cw\"/\"ccw\"), and use these step sizes:
    - 90° turn: 68 steps
    - 180° turn: 136 steps
    - 360° turn: 272 steps
- For forward/backward: both M1_dir and M2_dir are the same (\"cw\" or \"ccw\").
- If the user asks for multiple moves, return a JSON list of commands.
- If the input is not a movement command, reply with: NO_COMMAND

Examples:
- \"Go forward 100 steps\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"cw\", \"speed\": 300, \"step_size\": 100}
- \"Turn left 90 degrees\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"ccw\", \"speed\": 300, \"step_size\": 68}
- \"Kannst du 200 Schritte vorwärts gehen?\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"cw\", \"speed\": 300, \"step_size\": 200}
- \"Dön 180 derece\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"ccw\", \"speed\": 300, \"step_size\": 136}
- \"Bir tam tur at\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"ccw\", \"speed\": 300, \"step_size\": 272}
- \"Turn around three times\" → {\"M1_dir\": \"cw\", \"M2_dir\": \"ccw\", \"speed\": 300, \"step_size\": 816}
- \"Switch to German\" → NO_COMMAND
"""
chat_hist = [{"role":"system","content":SYSTEM_PROMPT}]

def gpt(prompt:str, temp:float)->str:
    chat_hist.append({"role":"user","content":prompt})
    reply = openai_client.chat.completions.create(
        model="gpt-4o", messages=chat_hist, temperature=temp
    ).choices[0].message.content.strip()
    chat_hist.append({"role":"assistant","content":reply})
    print(f"🧠 [gpt-4o]", reply)
    return reply

def validate_and_correct_commands(cmds: List[dict]) -> List[dict]:
    """Validate and correct step sizes for turns"""
    corrected_cmds = []
    
    for cmd in cmds:
        corrected_cmd = cmd.copy()
        
        # Check if this is a turn command (different directions)
        if cmd.get('M1_dir') != cmd.get('M2_dir'):
            step_size = cmd.get('step_size', 0)
            
            # Common turn step sizes that should be corrected
            if step_size == 216:  # Wrong full turn
                corrected_cmd['step_size'] = 272
                print(f"🔧 Corrected step_size from 216 to 272 (full turn)")
            elif step_size == 108:  # Wrong half turn
                corrected_cmd['step_size'] = 136
                print(f"🔧 Corrected step_size from 108 to 136 (half turn)")
            elif step_size == 54:  # Wrong quarter turn
                corrected_cmd['step_size'] = 68
                print(f"🔧 Corrected step_size from 54 to 68 (quarter turn)")
            elif step_size == 162:  # Wrong three-quarter turn
                corrected_cmd['step_size'] = 204
                print(f"🔧 Corrected step_size from 162 to 204 (three-quarter turn)")
        
        corrected_cmds.append(corrected_cmd)
    
    return corrected_cmds

def get_cmds(txt:str)->Optional[List[dict]]:
    try: obj=json.loads(txt); return validate_and_correct_commands(obj if isinstance(obj,list) else [obj])
    except: pass
    m=re.search(r"```(?:json)?\s+(.*?)```",txt,re.S)
    if m:
        try: obj=json.loads(m.group(1)); return validate_and_correct_commands(obj if isinstance(obj,list) else [obj])
        except: pass
    return None

YES=("execute","run","go","yes","onayla","evet","uygula","ja","oui","sí")
NO =("cancel","no","hayır","iptal","nein","non")

def recognize_with_whisper():
    import tempfile
    import soundfile as sf
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300  # adjust for your mic/environment
    recognizer.pause_threshold = 0.8   # seconds of silence to consider as end of phrase
    with sr.Microphone() as source:
        print("🎙️ Listening... (auto-stop on short silence)")
        audio = recognizer.listen(source, timeout=3)  # Wait up to 3s for speech to start
        print("🛑 Recording stopped.")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio.get_wav_data())
            temp_wav = f.name
    import whisper
    model = whisper.load_model("medium")
    result = model.transcribe(temp_wav, language=None)
    text = result["text"].strip()
    print(f"📝 Whisper recognized: {text}")
    return text

def publish_command(cmd):
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.publish(MQTT_TOPIC, json.dumps(cmd))
    print(f"📡 Published to {MQTT_TOPIC}: {cmd}")
    client.disconnect()

# ═════════════════════ MAIN LOOP ════════════════════════════════════════════
def main()->None:
    pending = None
    print("🎤 Robot agent active…  (Ctrl+C quits)")
    print("🌍 Whisper STT + OpenAI TTS + GPT-4o for robot commands!")
    
    while True:
        try:
            utter = recognize_with_whisper()
            if not utter:
                print("🤷 not understood")
                continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error during recognition: {e}")
            continue

        # Check if this is just a language switch request
        if is_language_switch_request(utter):
            # Use explicit language detection for switch requests
            explicit_lang = detect_explicit_language_request(utter)
            if explicit_lang:
                detected_lang = explicit_lang
                print(f"🔍 Explicit language switch detected: {detected_lang}")
            else:
                # Fallback to auto-detection if explicit detection fails
                detected_lang = auto_detect_language(utter) or "en-US"
            
            lang_names = {"en-US": "English", "de-DE": "German", "tr-TR": "Turkish", 
                         "fr-FR": "French", "es-ES": "Spanish", "it-IT": "Italian", "ru-RU": "Russian"}
            speak(f"Switched to {lang_names.get(detected_lang, detected_lang)}. How can I help you?", detected_lang)
            continue

        # Detect language from the recognized text (like ChatGPT)
        detected_lang = auto_detect_language(utter)
        if not detected_lang:
            detected_lang = "en-US"  # Default fallback
        
        print(f"🔍 Detected language: {detected_lang}")

        low=utter.lower()
        if pending:
            if any(w in low for w in YES):
                speak("Executing.", detected_lang)
                for c in pending:
                    # Only send supported keys for Robo Pro, but swap directions
                    cmd = {k: c[k] for k in ['M1_dir', 'M2_dir', 'speed', 'step_size'] if k in c}
                    # Swap directions
                    for dir_key in ['M1_dir', 'M2_dir']:
                        if dir_key in cmd:
                            if cmd[dir_key] == 'cw':
                                cmd[dir_key] = 'ccw'
                            elif cmd[dir_key] == 'ccw':
                                cmd[dir_key] = 'cw'
                    
                    print(f"🤖 Sending command: {cmd}")
                    publish_command(cmd)
                    time.sleep(1.0)
                pending=None; continue
            if any(w in low for w in NO):
                speak("Cancelled.", detected_lang); pending=None; continue
            speak("Say 'execute' to confirm, or modify the plan.", detected_lang); continue

        try:
            reply = gpt(utter, 0.2)
        except Exception as err:
            print("⚠️ GPT-4o failed:", err)
            speak("Sorry, I could not process your request.", detected_lang)
            continue

        # If GPT says NO_COMMAND, do not prompt for execution or send to robot
        if reply.strip() == "NO_COMMAND":
            speak("OK, language or context switched. Awaiting your robot command.", detected_lang)
            continue

        if (cmds:=get_cmds(reply)):
            pending=cmds; speak("Plan ready. Say execute to run.", detected_lang)
        else:
            speak(reply, detected_lang)

    if mqtt_client:
        mqtt_client.disconnect()

# ════════════════════════════════════════════════════════════════════════════
if __name__=="__main__":
    main()