import paho.mqtt.client as mqtt
import json
import time

client = mqtt.Client()
client.connect("test.mosquitto.org", 1883)

def on_connect(client, userdata, flags, rc):
    print("✅ Connected")
    payload = {
        "action": "MOVE_FORWARD",
        "turn_direction": "LEFT",
        "angle": 0,
        "x_center": 300,
        "height": 100
    }
    client.publish("txt4/action", json.dumps(payload))
    print("📤 Sent:", payload)
    time.sleep(2)
    client.disconnect()

client.on_connect = on_connect
client.connect("test.mosquitto.org", 1883)
client.loop_forever()