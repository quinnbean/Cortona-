import os
from openai import OpenAI

# Get API key
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("❌ OPENAI_API_KEY not set!")
    print("Run: export OPENAI_API_KEY='your-key-here'")
    exit(1)

client = OpenAI(api_key=api_key)

print("✅ OpenAI client initialized")
print(f"API Key starts with: {api_key[:10]}...")

# Test with TTS first (to generate test audio)
print("\n📢 Generating test audio with TTS...")
try:
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input="Hello Jarvis, can you hear me? Open YouTube please."
    )
    
    # Save the audio
    with open("test_audio.mp3", "wb") as f:
        for chunk in response.iter_bytes():
            f.write(chunk)
    print("✅ Test audio saved to test_audio.mp3")
    
    # Now transcribe it back
    print("\n🎤 Transcribing with Whisper...")
    with open("test_audio.mp3", "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )
    
    print(f"✅ Transcription: {transcript}")
    
    # Clean up
    os.remove("test_audio.mp3")
    print("\n🎉 Whisper API is working correctly!")
    
except Exception as e:
    print(f"❌ Error: {e}")
