import asyncio
import edge_tts
import json
from collections import defaultdict

async def main():
    voices = await edge_tts.list_voices()
    groups = defaultdict(dict)
    
    for v in voices:
        locale = v['Locale']
        short_name = v['ShortName']
        gender = v['Gender']
        
        # Make a friendly name
        # e.g., en-US-AriaNeural -> Aria (Female)
        name_part = short_name.split('-')[-1].replace('Neural', '')
        friendly_name = f"{name_part} ({gender})"
        
        groups[locale][friendly_name] = short_name

    with open('edge_voices.json', 'w', encoding='utf-8') as f:
        json.dump(groups, f, indent=4)
        
    print("Successfully generated edge_voices.json")

if __name__ == '__main__':
    asyncio.run(main())
