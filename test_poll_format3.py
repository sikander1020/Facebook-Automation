import urllib.request, urllib.parse, json, re

topic = 'A funny story about a smart dog trying to steal a cookie from the kitchen'
MASTER_PROMPT = """You are a Senior AI Software Architect and Hollywood Cartoon Director.
Generate a complete Production Document for a 2D Cartoon based on the topic: "{topic}".
The output MUST be strictly valid JSON without any markdown code blocks or extra text outside the JSON.
CRITICAL: Generate EXACTLY 3 scenes. Do not exceed 3 scenes. Generate a maximum of 2 characters. Keep script lines under 3 per scene. This is to keep the output concise.

Generate the JSON exactly matching this structure:
{{
  "story": {{
    "title": "Story Title",
    "summary": "Short engaging summary",
    "genre": "Genre",
    "target_age": "Target Age",
    "moral": "Moral of the story"
  }},
  "characters": [
    {{
      "id": "char_01",
      "name": "Character Name",
      "age": "Age",
      "appearance": "Extremely detailed description for image generation (clothes, colors, hair, face). Must be used exactly for character consistency.",
      "personality": "Short personality description",
      "voice_style": "Voice acting instructions"
    }}
  ],
  "scenes": [
    {{
      "scene_number": 1,
      "location": "Location Name",
      "time_of_day": "Day/Night",
      "environment": "Detailed background description",
      "mood": "Lighting and mood",
      "image_prompt": "Professional midjourney style prompt for 2D flat vector cartoon, maintaining character consistency.",
      "animation_prompt": "Instructions for camera and character movement",
      "sound_effects": ["Wind", "Door creaking"],
      "script": [
        {{
          "type": "narration",
          "text": "English narration text"
        }},
        {{
          "type": "dialogue",
          "speaker": "Character Name",
          "text": "Urdu dialogue written in English alphabet (Roman Urdu)"
        }}
      ]
    }}
  ],
  "youtube_metadata": {{
    "seo_title": "Clickbait SEO Title",
    "thumbnail_prompt": "Highly visual prompt for YouTube thumbnail generation",
    "tags": ["tag1", "tag2"]
  }}
}}

Make sure the JSON is valid. Do not include ```json tags.
"""
prompt = MASTER_PROMPT.format(topic=topic)
url = 'https://text.pollinations.ai/'
payload = {
    'messages': [
        {'role': 'user', 'content': prompt}
    ],
    'jsonMode': True,
    'model': 'llama'
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req, timeout=90).read().decode('utf-8')
print('RAW OUTPUT LENGTH:', len(res))
try:
    clean_json = re.sub(r',\s*([\]}])', r'\1', res)
    data = json.loads(clean_json)
    print('JSON PARSED SUCCESS!')
except Exception as e:
    print('JSON PARSE FAILED:', e)
    with open('failed_raw.json', 'w', encoding='utf-8') as f:
        f.write(res)
    print('Saved to failed_raw.json')
