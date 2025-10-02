import os
import openai
import paho.mqtt.client as mqtt
import json
from dotenv import load_dotenv

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "txt4/action"

# Load OpenAI API key
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Use GPT-4o for vision
OPENAI_VISION_MODEL = "gpt-4o"


def detect_p_with_openai(image_path):
    try:
        with open(image_path, "rb") as img_file:
            img_bytes = img_file.read()
        prompt = "Is there a parking sign (the letter 'P', as used for parking) visible in this image? Answer only YES or NO."
        response = openai.chat.completions.create(
            model=OPENAI_VISION_MODEL,
            messages=[
                {"role": "system", "content": "You are a visual parking sign detector."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"data": img_bytes, "detail": "low"}}
                ]}
            ],
            max_tokens=10
        )
        answer = response.choices[0].message.content.strip().lower()
        print(f"🔍 OpenAI Vision answer for {image_path}: {answer}")
        return "yes" in answer
    except Exception as e:
        print(f"❌ OpenAI Vision failed for {image_path}: {e}")
        return False

def send_park_command():
    cmd = {"M1_dir": "cw", "M2_dir": "cw", "speed": 200, "step_size": 100}  # Example: move forward to park
    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.publish(MQTT_TOPIC, json.dumps(cmd))
    print(f"📡 Sent park command: {cmd}")
    client.disconnect()

def main():
    image_dir = "received_images"
    for fname in os.listdir(image_dir):
        if fname.endswith(".jpg"):
            path = os.path.join(image_dir, fname)
            print(f"🔍 Processing {path}...")
            if detect_p_with_openai(path):
                send_park_command()
                break  # Only park at the first detected 'P'

if __name__ == "__main__":
    main() 