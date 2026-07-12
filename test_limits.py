import os
import google.generativeai as genai
from dotenv import load_dotenv
import time

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-pro-latest"
]

for m in models_to_test:
    try:
        model = genai.GenerativeModel(m)
        print(f"Testing {m}...")
        for i in range(35):
            response = model.generate_content("test")
            time.sleep(1)
        print(f"{m}: SUCCESS (35 requests passed)")
        break
    except Exception as e:
        print(f"{m} failed at request {i}: {e}")
