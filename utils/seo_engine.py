import json
import g4f

def generate_seo_metadata(topic):
    prompt = f"""You are an expert Social Media SEO manager. 
The user's video is about: "{topic}"

Please generate the following for this video to make it go viral on TikTok, Instagram Reels, and YouTube Shorts:
1. A catchy Title (under 60 characters)
2. A short Description (2 sentences max)
3. 5-7 highly relevant hashtags

Return ONLY a valid JSON object in the exact following format without any markdown or extra text:
{{
    "title": "Your Title Here",
    "description": "Your Description Here",
    "hashtags": "#tag1 #tag2 #tag3"
}}
"""
    try:
        # We use a reliable default model provided by g4f
        response = g4f.ChatCompletion.create(
            model=g4f.models.gpt_4o,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Clean potential markdown formatting from LLM response
        cleaned = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        return {
            "success": True,
            "title": data.get("title", "Awesome Video"),
            "description": data.get("description", "Check out this amazing content!"),
            "hashtags": data.get("hashtags", "#viral #trending #video")
        }
    except Exception as e:
        print(f"SEO Generation Error: {e}")
        # Fallback in case of failure so the upload can still proceed
        return {
            "success": True,
            "title": f"Amazing Video: {topic}",
            "description": f"Hope you enjoy this video about {topic}!",
            "hashtags": "#viral #trending #foryou",
            "error_note": str(e)
        }
