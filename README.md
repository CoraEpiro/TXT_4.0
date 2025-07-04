# TXT 4.0 Robot Project

This project contains Python scripts for robot control and image processing using OCR (Optical Character Recognition).

## Project Structure

- `P_detection.py` - Main OCR and parking detection script
- `speech_to_command.py` - Speech-to-command conversion
- `speech_to_text.py` - Speech-to-text processing
- `mac_subscriber.py` - MQTT subscriber for macOS
- `obstacle_handlign.py` - Obstacle handling logic
- `Image_from_server.py` - Image processing from server
- `test_sender.py` - Test script for sending commands
- `fixer.py` - Utility script for data fixing

## Directories

- `received_images/` - Contains processed images (not tracked by Git)
- `model_data/` - Contains training and validation data (not tracked by Git)
- `.venv/` - Python virtual environment (not tracked by Git)

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate  # On Windows
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Git Best Practices

This project follows Git best practices:

### Ignored Files
The following files and directories are ignored by Git:

- **System files**: `.DS_Store` (macOS)
- **Python cache**: `__pycache__/`, `*.pyc`, `*.pyo`
- **Virtual environments**: `.venv/`, `venv/`, `env/`
- **Large data files**: Images, model data, datasets
- **IDE files**: `.vscode/`, `.idea/`
- **Logs and temporary files**: `*.log`, `*.tmp`

### Committing Changes
1. Always check what files are staged: `git status`
2. Only commit source code and configuration files
3. Never commit large data files, cache files, or system files
4. Use descriptive commit messages

### Running the Fix Script
If you encounter Git violations, run:
```bash
./fix_git_violations.sh
```

## Usage

### OCR and Parking Detection
```bash
python P_detection.py
```

### Speech Processing
```bash
python speech_to_command.py
```

## MQTT Configuration

The project uses MQTT for communication:
- Broker: `broker.hivemq.com`
- Port: `1883` (TCP)
- Topic: `txt4/action`

## Dependencies

- OpenCV (`cv2`)
- PaddleOCR
- NumPy
- paho-mqtt
- Other dependencies listed in `requirements.txt`

## Contributing

1. Follow the Git best practices outlined above
2. Test your changes before committing
3. Update documentation as needed
4. Use meaningful commit messages

## License

[Add your license information here] 