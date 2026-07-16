import sys, os
sys.path.append('e:/Facebook Automation')
from utils.ai_studio import generate_studio_media

print('Starting test')
filenames = generate_studio_media(
    media_type='video',
    prompt='a cute cat',
    model='svd',
    style='none',
    duration=5,
    aspect_ratio='1:1',
    count=1,
    upload_folder='e:/Facebook Automation/outputs'
)
print('Result:', filenames)
