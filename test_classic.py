import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print("--- CLASSIC SDK TEST ---")

try:
    # 1. List Models (The Classic Way)
    print("Listing models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" - Found: {m.name}")

    # 2. Try to Generate
    print("\nAttempting generation with 'gemini-1.5-flash'...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hello, are you there?")
    print(f"SUCCESS: {response.text}")

except Exception as e:
    print(f"\nClassic Test Failed: {e}")