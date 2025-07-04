import paho.mqtt.client as mqtt
import base64
import os
#from P_detection import *

BROKER = 'test.mosquitto.org'  # Replace with your Mac's IP if it changes
PORT = 1883
TOPIC = 'txt4/image'
SAVE_DIR = 'received_images'

os.makedirs(SAVE_DIR, exist_ok=True)
received_images = set()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker")
        client.subscribe(TOPIC)
    else:
        print("❌ Failed to connect, return code:", rc)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        print(f"📨 Received on {msg.topic}: {payload[:60]}...")

        # Expecting format: img_0:base64data
        if ":" in payload:
            name, b64data = payload.split(":", 1)

            # Remove data URL prefix if present
            if b64data.startswith("data:image"):
                b64data = b64data.split(",", 1)[1]

            filename = f"{name}.jpg"
            filepath = os.path.join(SAVE_DIR, filename)

            with open(filepath, "wb") as f:
                f.write(base64.b64decode(b64data))
            print(f"✅ Saved: {filepath}")

            received_images.add(name)
            if len(received_images) >= 4:
                print("✅ Received 4 images. Exiting...")
                client.disconnect()
        else:
            print("⚠️ Invalid payload format. Expected: img_X:base64data")

    except Exception as e:
        print("❌ Error:", e)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT, 60)
client.loop_forever()