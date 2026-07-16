import os
import requests
import sys

# Reconfigure stdout for utf-8 (emoji support)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration with placeholders (Replace with your actual API details)
API_URL = "https://api.example.com/v1/images"
API_KEY = "YOUR_API_KEY_HERE"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

OUTPUT_DIR = r"E:\Facebook Automation\media"

def setup_directory():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✅ Created directory: {OUTPUT_DIR}")

def fetch_image_list():
    """Fetches the list of image URLs from the API."""
    print("Fetching image list from API...")
    try:
        # NOTE: Using a timeout and placeholder URL
        response = requests.get(API_URL, headers=HEADERS, timeout=10)
        
        # For demonstration, if the placeholder fails, we return an empty list
        if response.status_code != 200:
            print(f"⚠️ API returned status {response.status_code}. (Expected if using placeholder URL)")
            return []
            
        data = response.json()
        return data.get("image_urls", [])
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch from API: {e}")
        return []

def download_images(image_urls):
    """Downloads images from the provided URLs."""
    if not image_urls:
        print("No images to download.")
        return

    for i, url in enumerate(image_urls):
        try:
            print(f"Downloading {url}...")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                ext = url.split('.')[-1].split('?')[0]
                if ext not in ['jpg', 'jpeg', 'png', 'gif']:
                    ext = 'jpg' # Default fallback
                
                filename = os.path.join(OUTPUT_DIR, f"image_{i+1}.{ext}")
                with open(filename, "wb") as f:
                    f.write(response.content)
                print(f"✅ Saved: {filename}")
            else:
                print(f"❌ Failed to download {url} (Status: {response.status_code})")
        except Exception as e:
            print(f"❌ Error downloading {url}: {e}")

def main():
    print("="*50)
    print("MEDIA FETCHER STARTING")
    print("="*50)
    
    setup_directory()
    
    # In a real scenario, this would fetch actual URLs.
    image_urls = fetch_image_list()
    
    # Fallback for demonstration purposes so the script does something
    if not image_urls:
        print("Using demonstration URLs since API fetch failed/is a placeholder...")
        image_urls = [
            "https://picsum.photos/200/300.jpg",
            "https://picsum.photos/250/250.jpg"
        ]
        
    download_images(image_urls)
    
    print("="*50)
    print("MEDIA FETCHER COMPLETE")
    print("="*50)

if __name__ == "__main__":
    main()
