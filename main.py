import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from newsapi import NewsApiClient
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Load environment variables
load_dotenv(override=True)

NEWS_API_KEY = os.getenv('NEWS_API_KEY')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not NEWS_API_KEY or not GOOGLE_API_KEY:
    raise ValueError("Missing API keys in .env file.")

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
genai_client = genai.Client(api_key=GOOGLE_API_KEY)

# Directory setup
images_dir = Path('images')
images_dir.mkdir(exist_ok=True)

# Rate limiting
last_google_api_call_time = None
API_CALL_DELAY_SECONDS = 2

# --- CONFIGURATION ---
STORY_COUNT = 10

def wait_for_api_cooldown():
    global last_google_api_call_time
    if last_google_api_call_time is not None:
        elapsed = time.time() - last_google_api_call_time
        if elapsed < API_CALL_DELAY_SECONDS:
            time.sleep(API_CALL_DELAY_SECONDS - elapsed)
    last_google_api_call_time = time.time()

def clean_json_text(text):
    text = text.strip()
    if text.startswith('```json'): text = text.split('```json')[1]
    elif text.startswith('```'): text = text.split('```')[1]
    if text.endswith('```'): text = text.split('```')[0]
    return text.strip()

def fetch_stories(count):
    stories = []
    print(f"  Fetching {count} stories...")
    try:
        top_headlines = newsapi.get_top_headlines(country='us', page_size=15)
        raw_articles = top_headlines.get('articles', [])
        for i, article in enumerate(raw_articles):
            if i >= count: break
            stories.append({
                'id': i + 1,
                'title': article.get('title', 'Unknown Title'),
                'source': article.get('source', {}).get('name', 'Unknown Source'),
                'url': article.get('url', '#'),
                'description': article.get('description', '') or "No description available."
            })
    except Exception as e:
        print(f"  News API Error: {e}")
    return stories

def generate_waldo_theme(stories):
    wait_for_api_cooldown()
    print("  Inventing a Waldo-style Wimmelbilder theme...")
    titles = [s['title'] for s in stories]
    
    # Archetypes based on classic Martin Handford wimmelbilder
    archetypes = [
        "A sprawling medieval battle with ridiculous siege engines",
        "A multi-level futuristic airport with alien travelers",
        "A massive underwater coral city with submarine-taxis",
        "A giant chocolate factory with winding pipes",
        "A chaotic pirate harbor with multiple sinking ships",
        "A busy prehistoric valley with dinosaurs building a city",
        "A frantic Hollywood movie set with dozens of films being shot"
    ]
    
    prompt = f"""
    You are a 'Where's Waldo' (Wimmelbilder) illustrator. 
    Analyze these headlines: {titles}
    
    Task: 
    1. Select ONE base from: {archetypes}.
    2. Add a unique twist that reflects the mood of today's news.
    3. Ensure the scene is 'Wimmelbilder'—extremely dense, packed with hundreds of tiny people and sub-plots.
    
    Return ONLY the theme description. No JSON.
    """
    try:
        response = genai_client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        return response.text.strip()
    except:
        return "A chaotic isometric city festival with hundreds of tiny interactive stalls."

def generate_memory_palace_concept(stories, theme):
    wait_for_api_cooldown()
    print(f"  Designing Scene: {theme}")
    
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])
    prompt = f"""
    Create a 'Where's Waldo' style Memory Palace.
    Theme: {theme}
    Headlines: {story_text}

    Logic:
    1. Use literal visual puns (e.g. 'Inflated Pig' for 'Inflation').
    2. Symbols must pop with Neon colors against the busy background.
    3. Ground objects within the {theme}.

    Return JSON:
    {{
        "setting_description": "A dense Wimmelbilder illustration with black ink lines...",
        "story_elements": [
            {{ "id": 1, "visual_cue": "...", "mnemonic_explanation": "...", "assigned_zone": "Foreground Left" }}
        ]
    }}
    """
    response = genai_client.models.generate_content(
        model='gemini-2.0-flash', contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(clean_json_text(response.text))

def generate_image(scene_concept):
    wait_for_api_cooldown()
    print("  Painting Waldo Illustration...")
    visual_prompt = f"""
    STYLE: 'Where's Waldo' (Wimmelbilder) by Martin Handford. 
    TECHNICAL: Isometric view, clean black ink outlines, flat vibrant colors. 
    COMPOSITION: Extremely high density. Packed with hundreds of tiny people.
    THEME: {scene_concept['setting_description']}
    MNEMONIC SYMBOLS: """
    for element in scene_concept['story_elements']:
        visual_prompt += f"\n- {element['visual_cue']} (make it stand out)"
    
    response = genai_client.models.generate_content(
        model='gemini-2.5-flash-image', contents=visual_prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"])
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data: return Image.open(BytesIO(part.inline_data.data))
    return None

def find_coordinates(image, scene_concept):
    wait_for_api_cooldown()
    print("  Locating mnemonics...")
    items = [f"ID {e['id']}: {e['visual_cue']}" for e in scene_concept['story_elements']]
    prompt = f"Locate these in the image. Return JSON: {{ 'locations': [ {{ 'id': 1, 'x': 10, 'y': 20 }}, ... ] }}. Items: {items}"
    response = genai_client.models.generate_content(
        model='gemini-2.0-flash', contents=[prompt, image],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    return json.loads(clean_json_text(response.text))['locations']

def generate_html(stories, locations, image_filename):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NewsMap: Waldo Mode</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #f0f4f8; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; margin: 0; padding: 20px 0; }}
            .canvas-container {{ position: relative; width: 100%; max-width: 1200px; border: 4px solid #2b6cb0; border-radius: 12px; overflow: hidden; }}
            .main-image {{ width: 100%; height: auto; display: block; }}
            
            /* Numbers restored to markers */
            .news-marker {{ 
                position: absolute; width: 24px; height: 24px; 
                background: rgba(66, 153, 225, 0.8); backdrop-filter: blur(2px);
                border: 2px solid white; border-radius: 50%; cursor: pointer; 
                transform: translate(-50%, -50%); z-index: 10;
                display: flex; justify-content: center; align-items: center;
                color: white; font-weight: bold; font-size: 12px; transition: all 0.2s;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            }}
            .news-marker.active {{ width: 34px; height: 34px; background: #2b6cb0; font-size: 14px; opacity: 1; }}

            .story-card {{
                position: fixed; bottom: -100%; left: 0; right: 0;
                background: white; padding: 20px; border-radius: 20px 20px 0 0;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.2); transition: bottom 0.3s;
                z-index: 1000; max-width: 600px; margin: 0 auto;
            }}
            .story-card.active {{ bottom: 0; }}
            .overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.3); z-index: 900; display: none; }}
            .overlay.active {{ display: block; }}
            .mnemonic-box {{ background: #ebf8ff; border-left: 4px solid #4299e1; padding: 10px; margin: 10px 0; font-size: 13px; font-style: italic; }}
            .read-btn {{ display: block; width: 100%; background: #4299e1; color: white; text-align: center; padding: 12px 0; border-radius: 8px; text-decoration: none; font-weight: bold; }}
            
            @media (max-width: 768px) {{ .news-marker {{ width: 22px; height: 22px; font-size: 11px; }} }}
        </style>
    </head>
    <body>
        <div class="canvas-container">
            <img src="images/{image_filename}" class="main-image">
    """
    for story in stories:
        loc = next((l for l in locations if l['id'] == story['id']), {'x': 50, 'y': 50})
        # RESTORED ID NUMBER TO MARKER
        html += f'<div class="news-marker" onclick="openStory({story["id"]})" id="marker-{story["id"]}" style="top: {loc["y"]}%; left: {loc["x"]}%;">{story["id"]}</div>'
    
    html += '</div><div class="overlay" onclick="closeAll()"></div>'
    
    for story in stories:
        html += f"""
            <div class="story-card" id="card-{story['id']}">
                <h3 style="margin-top:0;">{story['title']}</h3>
                <div class="mnemonic-box">🧠 <strong>Hook:</strong> {story.get('mnemonic_explanation')}</div>
                <p>{story['description'][:150]}...</p>
                <a href="{story['url']}" target="_blank" class="read-btn">Read More</a>
            </div>
        """
    html += """
        <script>
            function openStory(id) {
                closeAll();
                document.getElementById('card-' + id).classList.add('active');
                document.getElementById('marker-' + id).classList.add('active');
                document.querySelector('.overlay').classList.add('active');
            }
            function closeAll() {
                document.querySelectorAll('.story-card').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('.news-marker').forEach(m => m.classList.remove('active'));
                document.querySelector('.overlay').classList.remove('active');
            }
        </script>
    </body></html>
    """
    with open('index.html', 'w', encoding='utf-8') as f: f.write(html)

def main():
    stories = fetch_stories(STORY_COUNT)
    if not stories: return
    
    theme = generate_waldo_theme(stories)
    concept = generate_memory_palace_concept(stories, theme)
    
    for story in stories:
        for elem in concept['story_elements']:
            if elem['id'] == story['id']:
                story['mnemonic_explanation'] = elem.get('mnemonic_explanation')
    
    image = generate_image(concept)
    if image:
        img_name = "index.png"
        image.save(images_dir / img_name)
        locs = find_coordinates(image, concept)
        generate_html(stories, locs, img_name)
        
        # AUTOMATED GIT UPLOAD (Optional, relies on git command availability)
        try:
            os.system('git add .')
            os.system(f'git commit -m "Auto Update: {time.ctime()}"')
            os.system('git push origin main')
            print("Successfully pushed to GitHub!")
        except Exception as e:
            print(f"Git upload failed: {e}")

if __name__ == "__main__":
    main()