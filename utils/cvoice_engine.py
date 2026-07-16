import urllib.request
import json
import os

CVOICE_API_KEY = "cvai_3f48f084e5fa8968e15eb5c5c4c5f9010b2512baa6e7a2e5"
CVOICE_API_URL = "https://cvoice.ai/api/tts"
DATASET_URL = "https://cvoice.ai/dataset_search.json"

def fetch_cvoice_voices():
    """
    Fetches the list of voices from cvoice.ai.
    Returns a list of dicts with 'ShortName' and 'FriendlyName'.
    """
    try:
        req = urllib.request.Request(DATASET_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            voices = []
            # Only taking top 200 to keep it manageable, sorted by fame_score if possible
            sorted_data = sorted(data, key=lambda x: x.get('fame_score', 0), reverse=True)
            for item in sorted_data[:200]:
                voices.append({
                    "ShortName": f"cvoice-{item['id']}",
                    "FriendlyName": f"CVoice: {item['name']} ({', '.join(item.get('occupations', []))})"
                })
            return voices
    except Exception as e:
        print(f"[CVoice] Error fetching dataset: {e}")
        return []

def generate_cvoice_speech(text, voice_id, output_path):
    """
    Generates speech using CVoice.ai API.
    voice_id comes in as 'cvoice-12345', we strip the 'cvoice-' prefix.
    """
    if voice_id.startswith('cvoice-'):
        voice_id = voice_id.replace('cvoice-', '')
        
    payload = json.dumps({
        'voice_id': voice_id,
        'text': text
    }).encode('utf-8')
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/json',
        'X-API-Key': CVOICE_API_KEY
    }
    
    print(f"[CVoice] Generating audio for voice {voice_id}...")
    try:
        req = urllib.request.Request(CVOICE_API_URL, data=payload, headers=headers)
        # Timeout set to 120s as TTS generation can take time
        with urllib.request.urlopen(req, timeout=120) as response:
            if response.status == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.read())
                print(f"[CVoice] Saved audio to {output_path}")
                return True
            else:
                print(f"[CVoice] API Error: HTTP {response.status}")
                return False
    except Exception as e:
        print(f"[CVoice] Request failed: {e}")
        if hasattr(e, 'read'):
            print(f"[CVoice] Error Details: {e.read()}")
        return False
