import os
import json
import cv2
import numpy as np
from paddleocr import PaddleOCR
import paho.mqtt.client as mqtt

# Initialize OCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# Configuration
image_folder = "received_images"
image_width = 640
CLOSE_THRESHOLD = 100
X_MARGIN = 50
current_angle = 0  # initial orientation of robot

# ✅ MQTT: Use TCP connection (compatible with RoboPro)
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker (TCP)")
    else:
        print("❌ Failed to connect. Code:", rc)

client = mqtt.Client()  # 🚫 no "transport=websockets"
client.on_connect = on_connect
client.connect("broker.hivemq.com", 1883)  # ✅ TCP port
client.loop_start()

def calculate_shortest_turn(current_angle, target_angle):
    diff = (target_angle - current_angle) % 360
    return ("LEFT", diff) if diff <= 180 else ("RIGHT", 360 - diff)

def preprocess_for_ocr(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None, None
    img_resized = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2
    )
    return thresh, img_resized

def analyze_all_images():
    best_match = None

    for i in range(1, 5):
        img_path = os.path.join(image_folder, f"img_{i}.jpg")
        print(f"\n🔍 Processing {img_path}...")

        processed_img, color_img = preprocess_for_ocr(img_path)
        if processed_img is None:
            print("❌ Could not load or preprocess image.")
            continue

        contours, _ = cv2.findContours(processed_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h < 60 or w < 30:
                continue

            roi_bgr = color_img[y:y+h, x:x+w]
            results = ocr.ocr(roi_bgr, det=False, cls=False)

            for line in results:
                if line:
                    for word_info in line:
                        text = word_info[0]
                        print(f"   → Detected: {text}")
                        if 'P' in text.upper():
                            print(f"✅ 'P' found in image {i}")
                            if best_match is None or h > best_match['height']:
                                best_match = {
                                    "img_index": i,
                                    "img_path": img_path,
                                    "x_center": x + w / 2,
                                    "height": h
                                }

    return best_match

def determine_motor_command(x_center, height):
    if height > CLOSE_THRESHOLD and abs(x_center - image_width / 2) < X_MARGIN:
        # Park = gentle forward motion
        return {
            "M1_dir": "cw",
            "M2_dir": "cw",
            "speed": 200,
            "step_size": 100
        }

    elif height > CLOSE_THRESHOLD:
        if x_center < image_width / 2:
            # Turn Left
            return {
                "M1_dir": "ccw",
                "M2_dir": "cw",
                "speed": 300,
                "step_size": 90
            }
        else:
            # Turn Right
            return {
                "M1_dir": "cw",
                "M2_dir": "ccw",
                "speed": 300,
                "step_size": 90
            }
    else:
        # Move Forward
        return {
            "M1_dir": "cw",
            "M2_dir": "cw",
            "speed": 400,
            "step_size": 120
        }

# --- Main Execution ---
best = analyze_all_images()

if best:
    command = determine_motor_command(best['x_center'], best['height'])
    client.publish("txt4/action", json.dumps(command))
    print("📡 Sent command:", command)
else:
    client.publish("txt4/action", json.dumps({"M1_dir": "cw", "M2_dir": "cw", "speed": 0, "step_size": 0}))

# ✅ Publish to topic (RoboPro must subscribe to "txt4/action")

client.loop_stop()
client.disconnect()