import urllib.request
import urllib.parse
import json
import re
import random
import os
try:
    from json_repair import repair_json
except ImportError:
    repair_json = None

PROMPT_PART1 = """You are a Senior AI Software Architect and Hollywood Cartoon Director.
Generate Part 1 of a Production Document for a 2D Cartoon based on the topic: "{topic}".
The output MUST be strictly valid JSON without markdown code blocks.
CRITICAL: Generate a maximum of 2 characters. Keep all descriptions VERY short (1 sentence max).

CRITICAL RULES:
1. ONLY return the JSON object, absolutely no other text.
2. DO NOT use double quotes inside your string values. Use single quotes if needed.
3. Ensure the JSON is 100% perfectly formatted.

Output exactly in this JSON format:
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
      "appearance": "Detailed description for image generation (clothes, colors, hair).",
      "personality": "Personality description",
      "voice_style": "Voice acting instructions"
    }}
  ]
}}
"""

PROMPT_PART2 = """You are a Senior AI Software Architect and Hollywood Cartoon Director.
We already have the story and characters for a 2D Cartoon based on the topic: "{topic}".
Generate Part 2: The Scenes and YouTube Metadata.
The output MUST be strictly valid JSON without markdown code blocks.
CRITICAL: You MUST generate EXACTLY 3 scenes. It is strictly forbidden to return an empty array. Keep all descriptions VERY short (max 1 sentence). Keep script lines to EXACTLY 1 per scene. Keep sound effects to 1 per scene. This is strictly required to prevent token limits.

CRITICAL RULES:
1. ONLY return the JSON object, absolutely no other text.
2. DO NOT use double quotes inside your string values. Use single quotes if needed.
3. Ensure the JSON is 100% perfectly formatted.

Output exactly in this JSON format:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "location": "Location Name",
      "time_of_day": "Day/Night",
      "environment": "Background description",
      "mood": "Lighting and mood",
      "image_prompt": "Breathtaking ultra-detailed 3D Pixar Disney style animation still, cinematic lighting, volumetric rays, highly intricate, vibrant colors, masterpiece, 8k resolution",
      "animation_prompt": "Camera and movement instructions",
      "sound_effects": ["Sound 1", "Sound 2"],
      "script": [
        {{
          "type": "narration",
          "text": "Highly engaging and expressive storytelling narration in native Urdu (اردو), like a professional storyteller or Dadi Maa, using expressive punctuation (... ! ?)."
        }},
        {{
          "type": "dialogue",
          "speaker": "Character Name",
          "text": "Dialogue written in native Urdu script (اردو)"
        }}
      ]
    }}
  ],
  "youtube_metadata": {{
    "seo_title": "Clickbait SEO Title",
    "thumbnail_prompt": "Prompt for YouTube thumbnail generation",
    "tags": ["tag1", "tag2"]
  }}
}}
"""

def _call_pollinations(prompt: str, max_retries=3):
    import random
    url = f"https://text.pollinations.ai/?seed={random.randint(1, 999999)}"
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "jsonMode": True,
        "model": "openai"
    }
    data = json.dumps(payload).encode('utf-8')
    
    last_err = None
    for attempt in range(max_retries):
        result_text = None
        try:
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=90) as response:
                result_text = response.read().decode('utf-8')
            
            result_text = result_text.strip()
            
            # Robustly extract JSON block
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                result_text = result_text[start_idx:end_idx+1]
            
            clean_json = re.sub(r',\s*([\]}])', r'\1', result_text)
            try:
                return repair_json(clean_json, return_objects=True)
            except:
                return json.loads(clean_json, strict=False)
        except Exception as e:
            last_err = e
            print(f"Pollinations API attempt {attempt+1} failed: {e}")
            if result_text is not None:
                # Safely print on Windows to avoid charmap codec errors
                safe_text = result_text.encode('unicode_escape').decode('ascii', errors='replace')
                print(f"RAW TEXT RETURNED: {safe_text}")
            continue
            
    raise Exception(f"AI generation failed due to network or formatting error. Please try again. (Error: {last_err})")

def generate_studio_project(topic: str):
    try:
        # Call 1: Story and Characters
        part1 = _call_pollinations(PROMPT_PART1.format(topic=topic))
        
        # Call 2: Scenes and Metadata
        part2 = _call_pollinations(PROMPT_PART2.format(topic=topic))
        
        # Merge them
        final_data = {**part1, **part2}
        
        return {"success": True, "data": final_data}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    
    pass
