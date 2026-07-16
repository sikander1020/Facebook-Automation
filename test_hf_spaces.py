from gradio_client import Client
try:
    print("Testing fffiloni/AnimateDiff-Image-Init...")
    client = Client("fffiloni/AnimateDiff-Image-Init")
    print(client.view_api(return_format="dict"))
except Exception as e:
    print(e)
