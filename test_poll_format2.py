import urllib.request, json
topic = 'A funny story about a smart dog'
MASTER_PROMPT = """You are a Senior AI Software Architect and Hollywood Cartoon Director.
Generate a complete Production Document for a 2D Cartoon based on the topic.
The output MUST be strictly valid JSON.

Generate the JSON exactly matching this structure:
{
  "story": {
    "title": "Story Title"
  },
  "characters": [
    {
      "id": "char_01",
      "name": "Character Name"
    }
  ],
  "scenes": [
    {
      "scene_number": 1,
      "location": "Location Name"
    }
  ]
}
"""
payload = {
    'messages': [
        {'role': 'user', 'content': f'{MASTER_PROMPT}\nTopic: {topic}'}
    ],
    'jsonMode': True,
    'model': 'openai'
}
req = urllib.request.Request('https://text.pollinations.ai/', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req).read().decode('utf-8')
print("RESPONSE:", res)
