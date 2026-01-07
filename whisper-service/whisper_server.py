"""
Local Whisper Service for Cortona
Runs on localhost:5051 and provides speech-to-text transcription
"""

import os
import sys
import tempfile
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='[WHISPER] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Allow requests from Electron app

# Global whisper model (loaded once)
whisper_model = None

def load_model():
    """Load whisper model on startup"""
    global whisper_model
    try:
        import whisper
        logger.info("Loading Whisper model (base)...")
        whisper_model = whisper.load_model("base")
        logger.info("✅ Whisper model loaded successfully!")
        return True
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        return False

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'model_loaded': whisper_model is not None
    })

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe audio to text using Whisper"""
    if whisper_model is None:
        return jsonify({'error': 'Whisper model not loaded'}), 500
    
    try:
        # Get audio data from request
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name
        
        logger.info(f"Transcribing audio file: {tmp_path}")
        
        # Transcribe with Whisper
        result = whisper_model.transcribe(
            tmp_path,
            language='en',
            fp16=False  # Use FP32 for better compatibility on Mac
        )
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        text = result.get('text', '').strip()
        logger.info(f"Transcription: {text}")
        
        return jsonify({
            'success': True,
            'text': text
        })
        
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Load model on startup
    if load_model():
        logger.info("Starting Whisper service on http://localhost:5051")
        app.run(host='127.0.0.1', port=5051, debug=False)
    else:
        logger.error("Failed to start - could not load Whisper model")
        sys.exit(1)

