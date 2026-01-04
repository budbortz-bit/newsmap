import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Force reload the environment
load_dotenv(override=True)

api_key = os.getenv("GOOGLE_API_KEY")

print("--- DIAGNOSTIC START ---")

# CHECK 1: Is the key loaded?
if not api_key:
    print("CRITICAL ERROR: No API Key found! Check your .env file naming.")
else:
    # Print first 5 and last 3 chars to verify it's the NEW key (don't print the whole thing)
    print(f"API Key loaded: {api_key[:5]}...{api_key[-3:]}")

# CHECK 2: Force a simple generation (Bypass 'list_models')
try:
    print("\nAttempting to contact Gemini 1.5 Flash...")
    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello, are you working?"
    )
    print(f"SUCCESS! The API is working. Reply: {response.text}")

    # CHECK 3: Now try Imagen specifically
    print("\nAttempting to contact Imagen 3...")
    # This is the standard paid model name
    imagen_model = "imagen-3.0-generate-001" 
    
    # We just check if it generates an object, not the actual image bytes to save console space
    img_response = client.models.generate_image(
        model=imagen_model,
        prompt="A small red dot",
        config=types.GenerateImageConfig(number_of_images=1)
    )
    print(f"SUCCESS! Imagen is working. Model name to use: {imagen_model}")

except Exception as e:
    print(f"\nAPI REQUEST FAILED.")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {e}")

print("--- DIAGNOSTIC END ---")