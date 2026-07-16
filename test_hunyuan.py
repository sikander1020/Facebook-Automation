from gradio_client import Client

try:
    print("Testing prediction on Boldbug8/HunyuanVideo...")
    client = Client("Boldbug8/HunyuanVideo")
    result = client.predict(
        param_0="a funny cat walking on a table, realistic cinematic lighting",
        param_1="832x624",
        param_2="65",
        param_3=-1,
        param_4=10,
        param_5=1.0,
        param_6=7.0,
        param_7=6.0,
        api_name="/lambda"
    )
    print("Success:", result)
except Exception as e:
    print("Failed:", e)
