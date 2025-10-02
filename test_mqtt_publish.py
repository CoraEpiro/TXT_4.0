import paho.mqtt.client as mqtt
import json

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "txt4/action"

cmd = {"M1_dir": "cw", "M2_dir": "cw", "speed": 300, "step_size": 200}

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.publish(MQTT_TOPIC, json.dumps(cmd))
print(f"📡 Published to {MQTT_TOPIC}: {cmd}")
client.disconnect() 