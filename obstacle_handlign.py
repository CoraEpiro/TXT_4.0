#!/usr/bin/env python3
# hardcoded_right_bypass_ack.py
import json, time, base64, os
import cv2, numpy as np, paho.mqtt.client as mqtt

# MQTT
BROKER      = "broker.hivemq.com"
PORT        = 1883
TOPIC_IMG   = "txt4/obstacleImage"
TOPIC_CMD   = "txt4/action"
TOPIC_ACK   = "txt4/actionAck"      # TXT must publish {"done":true}

# Motion constants
SPD, TURN, FWD_S, FWD_L = 512, 72, 140, 300
DELAY_FALLBACK          = 3               # if no ACK arrives (seconds)

RIGHT_BYPASS = [
    {"type":"move", "M1_dir":"cw",  "M2_dir":"ccw", "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":TURN,  "M2_step_size":TURN },
    {"type":"move", "M1_dir":"cw",  "M2_dir":"cw",  "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":FWD_S, "M2_step_size":FWD_S},
    {"type":"move", "M1_dir":"ccw", "M2_dir":"cw",  "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":TURN,  "M2_step_size":TURN },
    {"type":"move", "M1_dir":"cw",  "M2_dir":"cw",  "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":FWD_L, "M2_step_size":FWD_L},
    {"type":"move", "M1_dir":"ccw", "M2_dir":"cw",  "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":TURN,  "M2_step_size":TURN },
    {"type":"move", "M1_dir":"cw",  "M2_dir":"cw",  "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":FWD_S, "M2_step_size":FWD_S},
    {"type":"move", "M1_dir":"cw",  "M2_dir":"ccw", "M1_speed":SPD, "M2_speed":SPD, "M1_step_size":TURN,  "M2_step_size":TURN }
]

LEFT_BYPASS  = [{**s, "M1_dir":"ccw" if s["M1_dir"]=="cw" else "cw",
                       "M2_dir":"ccw" if s["M2_dir"]=="cw" else "cw"} for s in RIGHT_BYPASS]
FORWARD = [{"type":"move","M1_dir":"cw","M2_dir":"cw","M1_speed":SPD,"M2_speed":SPD,
            "M1_step_size":FWD_S,"M2_step_size":FWD_S}]

# Simple heuristic → left / right / forward
def decide(img):
    g   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _,t = cv2.threshold(cv2.GaussianBlur(g,(7,7),0),60,255,cv2.THRESH_BINARY_INV)
    cnt,_ = cv2.findContours(t,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not cnt: return "forward"
    x,y,w,h = cv2.boundingRect(max(cnt,key=cv2.contourArea))
    cx, mid = x+w//2, img.shape[1]//2
    if w*h<800: return "forward"
    return "right" if cx<=mid else "left"

# Publish step-by-step, waiting for ACK
ack_flag = False
def on_ack(_c,_u,_m):
    global ack_flag
    ack_flag = True

def send_sequence(seq):
    global ack_flag
    for i,cmd in enumerate(seq,1):
        ack_flag = False
        CLIENT.publish(TOPIC_CMD,json.dumps(cmd))
        print(f"🚗 {i}/{len(seq)} → {cmd}")
        t0 = time.time()
        while not ack_flag and time.time()-t0 < DELAY_FALLBACK:
            CLIENT.loop(timeout=0.2)
        if not ack_flag:
            print("⚠️  no ACK; continuing after fallback delay")

# MQTT image handler
def on_image(_c,_u,msg):
    b64 = msg.payload.decode().split("base64,",1)[-1]
    img = cv2.imdecode(np.frombuffer(base64.b64decode(b64),np.uint8), cv2.IMREAD_COLOR)
    if img is None: return
    dir_ = decide(img)
    print(f"🤖 decision: {dir_.upper()}")
    seq  = {"left":LEFT_BYPASS,"right":RIGHT_BYPASS,"forward":FORWARD}[dir_]
    send_sequence(seq)

def on_connect(c,*_):
    c.subscribe(TOPIC_IMG)
    c.subscribe(TOPIC_ACK)
    c.message_callback_add(TOPIC_IMG,on_image)
    c.message_callback_add(TOPIC_ACK,on_ack)
    print("📡 MQTT connected – listening")

# Main loop
CLIENT = mqtt.Client()
CLIENT.on_connect = on_connect
CLIENT.connect(BROKER, PORT, 60)
CLIENT.loop_start()

try:
    while True: time.sleep(0.5)
except KeyboardInterrupt:
    CLIENT.loop_stop(); CLIENT.disconnect()