import os
import fal_client

os.environ["FAL_KEY"] = "YOUR_API_KEY"

def test():
    try:
        print("Testing Fal AI Veo...")
        result = fal_client.subscribe(
            "fal-ai/veo",
            arguments={"prompt": "A cinematic shot of a cat drinking milk"}
        )
        print("Result:", result)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test()
