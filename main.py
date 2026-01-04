import os
import json
import time
import shutil
from datetime import datetime
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
    raise ValueError("Missing API keys in .env file")

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
genai_client = genai.Client(api_key=GOOGLE_API_KEY)

# Directory setup
images_dir = Path('images')
archives_dir = Path('archives')
images_dir.mkdir(exist_ok=True)
archives_dir.mkdir(exist_ok=True)

# Rate limiting
last_google_api_call_time = None
API_CALL_DELAY_SECONDS = 2

# --- CONFIGURATION ---
SECTIONS = [
    {
        "name": "Front Page",
        "filename": "index.html",
        "category": None, 
        "story_count": 10
    }
]

def wait_for_api_cooldown():
    global last_google_api_call_time
    if last_google_api_call_time is not None:
        elapsed = time.time() - last_google_api_call_time
        if elapsed < API_CALL_DELAY_SECONDS:
            time.sleep(API_CALL_DELAY_SECONDS - elapsed)
    last_google_api_call_time = time.time()

def clean_json_text(text):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()

def fetch_stories(category, count):
    stories = []
    print(f"  Fetching {count} stories...")
    try:
        top_headlines = newsapi.get_top_headlines(country='us', page_size=15) if not category else newsapi.get_top_headlines(category=category, country='us', page_size=15)
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

def generate_memory_palace_concept(stories, count):
    wait_for_api_cooldown()
    print("  Scouting Locations & Analyzing Vibe (Logic AI)...")
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])
    prompt = f"""
    Analyze these headlines.
    1. Pick an International location if mentioned, or a Cinematic Movie Scene vibe.
    2. Design a 'Sketchy Medical' style scene. 
    3. Return JSON only with 'chosen_location', 'theme_name', 'setting_description', and 'story_elements' (id, visual_cue, mnemonic_explanation, assigned_zone).
    
    Headlines:
    {story_text}
    """
    try:
        response = genai_client.models.generate_content(model='gemini-2.0-flash', contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=1.0))
        data = json.loads(clean_json_text(response.text))
        return data[0] if isinstance(data, list) else data
    except: return None

def generate_image(scene_concept, count):
    wait_for_api_cooldown()
    setting = scene_concept.get('setting_description', 'A cinematic world')
    
    print(f"  Painting the Scene (Image AI)...")
    
    visual_prompt = f"A SINGLE CONTINUOUS PANORAMIC SCENE: {setting}.\n"
    visual_prompt += "STYLE: 'Sketchy Medical' mnemonic illustration. Bold black ink outlines, flat cell-shading, vibrant saturated colors. Isometric wide-angle view.\n"
    
    visual_prompt += f"\nINTEGRATED MNEMONIC OBJECTS:\n"
    for element in scene_concept.get('story_elements', []):
        visual_prompt += f"- In the {element.get('assigned_zone', 'center')}: {element.get('visual_cue')} (Grounded naturally, NO TEXT).\n"
    
    visual_prompt += "\nRULES: NO text, NO labels. Professional digital art. NO white background."

    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash-image', 
            contents=visual_prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )
        if not response.candidates or not response.candidates[0].content.parts:
            return None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data))
        return None
    except Exception as e:
        print(f"  Image Gen Error: {e}")
        return None

def find_coordinates(image, scene_concept):
    wait_for_api_cooldown()
    items_str = "\n".join([f"ID {e['id']}: {e['visual_cue']}" for e in scene_concept['story_elements']])
    prompt = f"Find (x, y) coordinates (0-100) for centers of objects in this image. Return JSON: {{'locations': [{{'id':1,'x':10,'y':20}}]}}.\n{items_str}"
    try:
        response = genai_client.models.generate_content(model='gemini-2.0-flash', contents=[prompt, image], config=types.GenerateContentConfig(response_mime_type="application/json"))
        data = json.loads(clean_json_text(response.text))
        return data.get('locations', [])
    except: return []

def generate_html(section_config, stories, locations, image_filename, theme_name, target_file, is_archive=False):
    # Adjust path for archive files vs root files
    img_path = f"../images/{image_filename}" if is_archive else f"images/{image_filename}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NewsMap</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ background: #f0f4f8; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; margin: 0; padding: 20px 0; }}
            .canvas-container {{ position: relative; width: 95%; max-width: 1100px; border: 5px solid #2d3748; border-radius: 15px; overflow: hidden; }}
            .main-image {{ width: 100%; display: block; }}
            .news-marker {{ 
                position: absolute; width: 34px; height: 34px; 
                background: rgba(66, 153, 225, 0.45); backdrop-filter: blur(4px); 
                border: 2px solid white; border-radius: 50%; color: white;
                display: flex; justify-content: center; align-items: center; font-weight: bold; transform: translate(-50%, -50%); cursor: pointer; z-index: 10;
            }}
            @media (max-width: 600px) {{ .news-marker {{ width: 24px; height: 24px; font-size: 11px; }} }}
            .story-card {{ position: fixed; bottom: -100%; left: 0; right: 0; background: white; padding: 25px; border-radius: 25px 25px 0 0; transition: 0.4s; z-index: 1000; box-shadow: 0 -10px 40px rgba(0,0,0,0.3); }}
            .story-card.active {{ bottom: 0; }}
            .overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: none; z-index: 900; }}
            .overlay.active {{ display: block; }}
            .mnemonic-box {{ background: #ebf8ff; border-left: 5px solid #4299e1; padding: 12px; margin: 15px 0; font-style: italic; }}
        </style>
    </head>
    <body>
        <h1>NewsMap</h1>
        <div class="canvas-container">
            <img src="{img_path}" class="main-image">
    """
    for story in stories:
        loc = next((l for l in locations if l['id'] == story['id']), {'x': 10 * story['id'], 'y': 50})
        html += f'<div class="news-marker" onclick="openStory({story["id"]})" style="top: {loc["y"]}%; left: {loc["x"]}%;">{story["id"]}</div>'
    
    html += '</div><div class="overlay" onclick="closeAll()"></div>'
    
    for story in stories:
        html += f"""
            <div class="story-card" id="card-{story['id']}">
                <h3>{story['title']}</h3>
                <div class="mnemonic-box">🧠 Hook: {story.get('mnemonic_explanation', '')}</div>
                <p>{story['description']}</p>
                <a href="{story['url']}" target="_blank">Full Article</a>
                <button onclick="closeAll()">Close</button>
            </div>
        """
    html += """
        <script>
            function openStory(id) {
                closeAll();
                document.getElementById('card-' + id).classList.add('active');
                document.querySelector('.overlay').classList.add('active');
            }
            function closeAll() {
                document.querySelectorAll('.story-card').forEach(c => c.classList.remove('active'));
                document.querySelector('.overlay').classList.remove('active');
            }
        </script>
    </body></html>
    """
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(html)

def update_gallery():
    print("  Updating Archive Gallery...")
    # Sort files by newest timestamp first
    html_files = sorted(list(archives_dir.glob("*.html")), reverse=True)
    gallery_html = f"""
    <!DOCTYPE html><html><head><title>NewsMap Archive</title><style>
    body{{ font-family: sans-serif; padding: 40px; background: #f0f4f8; text-align: center; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
    .item {{ background: white; padding: 15px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
    img {{ width: 100%; border-radius: 8px; }}
    a {{ text-decoration: none; color: #4299e1; font-weight: bold; display: block; margin-top: 10px; }}
    </style></head><body><h1>Historical NewsMaps</h1><div class='grid'>
    """
    for h_file in html_files:
        # Extract timestamp for display
        display_name = h_file.stem.replace("_", " ").replace("Front Page", "")
        img_name = h_file.stem + ".png"
        gallery_html += f"""
        <div class='item'>
            <img src='images/{img_name}'>
            <a href='archives/{h_file.name}'>{display_name}</a>
        </div>
        """
    gallery_html += "</div></body></html>"
    with open("gallery.html", "w", encoding='utf-8') as f:
        f.write(gallery_html)

def main():
    # USES SECONDS TO ALLOW MULTIPLE RUNS PER DAY
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    for section in SECTIONS:
        stories = fetch_stories(section['category'], section['story_count'])
        if not stories: continue
        
        concept = generate_memory_palace_concept(stories, section['story_count'])
        if not concept: continue
        
        # Match mnemonics to stories
        for story in stories:
            for elem in concept.get('story_elements', []):
                if elem['id'] == story['id']:
                    story['mnemonic_explanation'] = elem.get('mnemonic_explanation', '')

        image = generate_image(concept, section['story_count'])
        if not image: continue

        # UNIQUE FILENAMES
        base_name = f"{run_timestamp}_{section['name'].replace(' ', '_')}"
        image_name = f"{base_name}.png"
        html_name = f"{base_name}.html"
        
        # Save unique image
        image.save(images_dir / image_name)
        
        # Locate mnemonics
        locations = find_coordinates(image, concept)
        
        # Generate Archive HTML (in archives folder)
        generate_html(section, stories, locations, image_name, concept.get('theme_name'), archives_dir / html_name, is_archive=True)
        
        # Update Main index.html (in root folder) for the "latest" view
        generate_html(section, stories, locations, image_name, concept.get('theme_name'), section['filename'], is_archive=False)
        
        # Rebuild the gallery grid
        update_gallery()
        
        try:
            os.system('git add .')
            os.system(f'git commit -m "Automated Run: {run_timestamp}"')
            os.system('git push origin main')
        except: print("Git failed")

if __name__ == "__main__":
    main()