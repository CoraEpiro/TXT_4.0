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
# ═════════════════════════════ CONFIG ═══════════════════════════════════════
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
FINETUNED_MODEL = os.getenv("FINETUNED_MODEL")
FALLBACK_MODEL = ""

MQTT_BROKER, MQTT_PORT, MQTT_TOPIC = "broker.hivemq.com", 1883, "txt4/action"

# OpenAI-TTS defaults (override in .env)
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "tts-1")   # or "tts-1-hd"
OPENAI_VOICE     = os.getenv("OPENAI_VOICE", "alloy")       # alloy / onyx …

# Optional loudness match for Coqui vs OpenAI (dB)
COQUI_GAIN_DB = float(os.getenv("COQUI_GAIN_DB", "0"))
# ═════════════════════ INITIALISE CLIENTS ═══════════════════════════════════
openai_client = OpenAI(api_key=OPENAI_API_KEY)

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# ═════════════════════ COQUI-TTS SETUP ══════════════════════════════════════
COQUI_MODELS: Dict[str, Tuple[str, Optional[str]]] = {
    "en-US": ("tts_models/en/ljspeech/tacotron2-DDC", None),
    "de-DE": ("tts_models/de/thorsten/tacotron2-DDC", None),
    "tr-TR": ("tts_models/tr/common-voice/glow-tts", None),
    "fr-FR": ("tts_models/fr/css10/vits", None),
    "es-ES": ("tts_models/es/mai/tacotron2-DDC", None),
    "it-IT": ("tts_models/multilingual/multi-dataset/your_tts", "it_0"),
}
MULTI_SPKR_MODEL = "tts_models/multilingual/multi-dataset/your_tts"
SPK_MAP = {"it-IT": "it_0", "fr-FR": "fr_0", "tr-TR": "tr_0",
           "en-US": "en_0", "de-DE": "de_0", "es-ES": "es_0"}

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

    # 1️⃣  OpenAI-TTS
    try:
        t0 = time.time()
        rsp = openai_client.audio.speech.create(
            model  = OPENAI_TTS_MODEL,
            voice  = OPENAI_VOICE,
            input  = clean,
            #format = "wav",
        )
        data, sr = sf.read(io.BytesIO(rsp.read()), dtype="float32")
        sd.play(data, sr); sd.wait()
        print(f"[🔊 OPENAI] {time.time()-t0:.2f}s • {len(data)} samples")
        return
    except Exception as err:
        print("OpenAI-TTS error → Coqui :", err)

    # 2️⃣  Coqui fallback
    tts, dflt = get_tts(lang)
    multi  = bool(getattr(tts, "speakers", []))
    spk_id = SPK_MAP.get(lang, dflt) if multi else None
    gain   = 10 ** (COQUI_GAIN_DB / 20)

    t0 = time.time()
    for chunk in _split(clean):
        wav = tts.tts(chunk, speaker=spk_id) if multi else tts.tts(chunk)
        wav = np.asarray(wav, dtype=np.float32) * gain   # ← safe scaling
        sd.play(wav, tts.synthesizer.output_sample_rate); sd.wait()
    print(f"[🔊 COQUI]  {time.time()-t0:.2f}s")

# ═════════════════════ LANG / INTENT HELPERS ════════════════════════════════
LANG_MAP = {"english":"en-US","ingilizce":"en-US","german":"de-DE","deutsch":"de-DE",
            "almanca":"de-DE","turkish":"tr-TR","türkçe":"tr-TR","french":"fr-FR",
            "français":"fr-FR","spanish":"es-ES","español":"es-ES",
            "italian":"it-IT","italiano":"it-IT"}
def detect_lang_switch(txt:str)->Optional[str]:
    low=txt.lower()
    for name,code in LANG_MAP.items():
        if re.search(rf"\b{re.escape(name)}\b",low) or f"switch to {name}" in low:
            return code
    return None

CMD_HINTS = ("forward","back","move","spin","turn","left","right","wait",
             "geri","ileri","dön","bekle","links","rechts")
likely_cmd = lambda t:any(w in t.lower() for w in CMD_HINTS)

# ═════════════════════ GPT + JSON PARSER ════════════════════════════════════
SYSTEM_PROMPT = "You are the robot command assistant."
chat_hist = [{"role":"system","content":SYSTEM_PROMPT}]

def gpt(prompt:str, model:str, temp:float)->str:
    chat_hist.append({"role":"user","content":prompt})
    reply = openai_client.chat.completions.create(
        model=model, messages=chat_hist, temperature=temp
    ).choices[0].message.content.strip()
    chat_hist.append({"role":"assistant","content":reply})
    print(f"🧠 [{model.split(':')[0]}]", reply)
    return reply

def get_cmds(txt:str)->Optional[List[dict]]:
    try: obj=json.loads(txt); return obj if isinstance(obj,list) else [obj]
    except: pass
    m=re.search(r"```(?:json)?\s+(.*?)```",txt,re.S)
    if m:
        try: obj=json.loads(m.group(1)); return obj if isinstance(obj,list) else [obj]
        except: pass
    return None

YES=("execute","run","go","yes","onayla","evet","uygula","ja","oui","sí")
NO =("cancel","no","hayır","iptal","nein","non")

# ═════════════════════ MAIN LOOP ════════════════════════════════════════════
def main()->None:
    rec, lang, pending = sr.Recognizer(), "en-US", None
    print("🎤 Robot agent active…  (Ctrl+C quits)")
    while True:
        try:
            with sr.Microphone() as src:
                rec.adjust_for_ambient_noise(src)
                print(f"🞡 Listening ({lang})…")
                audio=rec.listen(src,timeout=10,phrase_time_limit=15)
                utter=rec.recognize_google(audio,language=lang)
                print("🗣️",utter)
        except sr.WaitTimeoutError: continue
        except sr.UnknownValueError: print("🤷 not understood"); continue
        except KeyboardInterrupt: break

        if (new:=detect_lang_switch(utter)) and new!=lang:
            lang=new; speak(f"Language switched to {new}.",lang); continue

        low=utter.lower()
        if pending:
            if any(w in low for w in YES):
                speak("Executing.",lang)
                for c in pending:
                    mqtt_client.publish(MQTT_TOPIC,json.dumps(c)); time.sleep(1.0)
                pending=None; continue
            if any(w in low for w in NO):
                speak("Cancelled.",lang); pending=None; continue
            speak("Say 'execute' to confirm, or modify the plan.",lang); continue

        try:
            reply = gpt(utter, FINETUNED_MODEL, 0.0)
        except Exception as err:
            print("⚠️ Finetuned model failed → Falling back to GPT-4o:", err)
            reply = gpt(utter, "gpt-4o", 0.2)


        if (cmds:=get_cmds(reply)):
            pending=cmds; speak("Plan ready. Say execute to run.",lang)
        else:
            speak(reply,lang)

    mqtt_client.disconnect()

# ════════════════════════════════════════════════════════════════════════════
if __name__=="__main__":
    main()