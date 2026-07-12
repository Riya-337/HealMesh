import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("test")
    print("gemini-2.5-flash: SUCCESS")
except Exception as e:
    print("gemini-2.5-flash:", e)

try:
    model = genai.GenerativeModel("gemini-flash-lite-latest")
    response = model.generate_content("test")
    print("gemini-flash-lite-latest: SUCCESS")
except Exception as e:
    print("gemini-flash-lite-latest:", e)

try:
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content("test")
    print("gemini-2.5-flash-lite: SUCCESS")
except Exception as e:
    print("gemini-2.5-flash-lite:", e)
