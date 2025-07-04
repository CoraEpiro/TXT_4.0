import paho.mqtt.client as mqtt
import base64
import os
import subprocess

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "txt4/image"
SAVE_DIR = 'received_images'

os.makedirs(SAVE_DIR, exist_ok=True)
received_images = set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC)
        print(f"📡 Subscribed to topic: {TOPIC}")
    else:
        print("❌ Failed to connect. Code:", rc)

def on_message(client, userdata, msg):
    try:
        print(f"📨 Received message of {len(msg.payload)} bytes")

        payload = msg.payload.decode(errors="ignore")  # Avoid decode errors

        if ":" not in payload:
            print("⚠️ Invalid payload, missing ':'")
            return

        name, b64data = payload.split(":", 1)

        # Remove base64 prefix if present
        if b64data.startswith("data:image"):
            b64data = b64data.split(",", 1)[1]

        filename = f"{name.strip()}.jpg"
        filepath = os.path.join(SAVE_DIR, filename)

        # Write decoded image
        try:
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64data))
            print(f"✅ Image saved: {filepath}")
        except Exception as e:
            print("❌ Failed to decode/write image:", e)
            return

        received_images.add(name.strip())
        if len(received_images) >= 4:
            print("📷 Received 4 images. Running detection...")
            subprocess.run(["python3", "P_detection.py"])
            client.disconnect()

    except Exception as e:
        print("❌ Error in on_message:", e)

def on_log(client, userdata, level, buf):
    print("📒 MQTT Log:", buf)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_log = on_log  # optional for debugging

print("🚀 Waiting for images from robot...")
client.connect(BROKER, PORT)
client.loop_forever()
