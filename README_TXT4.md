# TXT4.0 Robot Vision System

## 🎯 Overview
This system receives images from a robot via MQTT, performs OCR to detect "P" signs, and sends motor commands back to the robot.

## ✅ System Status
**FIXED!** The architecture mismatch issues have been resolved. The system now works with ARM64-native dependencies.

## 🚀 Quick Start

### Option 1: Using the launcher script (Recommended)
```bash
./run_txt4.sh
```

### Option 2: Manual activation
```bash
# Activate the conda environment
conda activate txt4

# Run the subscriber
python mac_subscriber.py
```

## 📋 How It Works

1. **`mac_subscriber.py`** - Listens for MQTT messages on topic `txt4/image`
2. **Receives images** - Saves them as `img_1.jpg`, `img_2.jpg`, etc. in `received_images/` folder
3. **Triggers detection** - When 4 images are received, automatically runs `P_detection.py`
4. **OCR Processing** - Analyzes images to find "P" signs using PaddleOCR
5. **Motor Commands** - Sends commands to topic `txt4/action` for robot control

## 🔧 System Requirements

- **Python**: 3.10
- **Environment**: ARM64-native conda environment (`txt4`)
- **Dependencies**: All installed in the conda environment

## 📦 Dependencies (Auto-installed)

- `paho-mqtt` - MQTT communication
- `paddleocr` - OCR for text detection
- `paddlepaddle` - Deep learning framework
- `opencv-python` - Image processing
- `numpy` - Numerical computing
- `matplotlib` - Plotting (if needed)
- `pillow` - Image handling

## 🎮 Robot Integration

### MQTT Topics
- **Subscribe**: `txt4/image` - Receives base64-encoded images
- **Publish**: `txt4/action` - Sends motor commands

### Motor Command Format
```json
{
  "M1_dir": "cw",      // Motor 1 direction (cw/ccw)
  "M2_dir": "cw",      // Motor 2 direction (cw/ccw)
  "speed": 400,        // Speed (0-1000)
  "step_size": 120     // Step size
}
```

## 🛠️ Troubleshooting

### If you get architecture errors:
```bash
# Make sure you're in the correct environment
conda activate txt4

# Verify ARM64-native packages
python -c "import numpy, cv2, paho.mqtt.client; print('✅ All good!')"
```

### If P_detection.py fails:
- Check that all 4 images exist in `received_images/` folder
- Verify MQTT broker connection
- Check that robot is subscribed to `txt4/action` topic

## 📁 File Structure
```
TXT_4.0/
├── mac_subscriber.py      # Main subscriber (receives images)
├── P_detection.py         # OCR and motor command logic
├── run_txt4.sh           # Easy launcher script
├── received_images/       # Folder for received images
└── requirements.txt       # Dependencies list
```

## 🎯 Usage Example

1. **Start the system**:
   ```bash
   ./run_txt4.sh
   ```

2. **System output**:
   ```
   🚀 Starting TXT4.0 Robot Vision System...
   ✅ Environment activated: txt4
   📡 Starting MQTT subscriber...
   🚀 Waiting for images from robot...
   ✅ Connected to MQTT broker
   📡 Subscribed to topic: txt4/image
   ```

3. **When robot sends 4 images**:
   ```
   📨 Received message of 11489 bytes
   ✅ Image saved: received_images/img_1.jpg
   ...
   📷 Received 4 images. Running detection...
   🔍 Processing received_images/img_1.jpg...
   ✅ 'P' found in image 1
   📡 Sent command: {"M1_dir": "cw", "M2_dir": "cw", "speed": 200, "step_size": 100}
   ```

## 🔄 Environment Management

### To recreate the environment (if needed):
```bash
# Create new environment
conda create -n txt4 python=3.10 -y

# Activate
conda activate txt4

# Install core dependencies
conda install numpy pillow matplotlib opencv -y

# Install remaining dependencies
pip install paho-mqtt paddleocr paddlepaddle
```

## 📝 Notes

- The system automatically downloads PaddleOCR models on first run
- All dependencies are ARM64-native for Apple Silicon Macs
- The system waits for exactly 4 images before running detection
- Motor commands are sent to `txt4/action` topic for robot control

## 🎉 Success!

Your TXT4.0 system is now fully functional with:
- ✅ ARM64-native environment
- ✅ All dependencies working
- ✅ MQTT communication
- ✅ OCR detection
- ✅ Motor command generation 