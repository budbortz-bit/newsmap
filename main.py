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
    raise ValueError("Missing API keys in .env file")

newsapi = NewsApiClient(api_key=NEWS_API_KEY)
genai_client = genai.Client(api_key=GOOGLE_API_KEY)

# Directory setup
images_dir = Path('images')
images_dir.mkdir(exist_ok=True)

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
    if text.startswith('```json'):
        text = text.split('```json')[1]
    elif text.startswith('```'):
        text = text.split('```')[1]
    if text.endswith('```'):
        text = text.split('```')[0]
    return text.strip()

def fetch_stories(category, count):
    stories = []
    print(f"  Fetching {count} stories...")
    try:
        if category:
            top_headlines = newsapi.get_top_headlines(category=category, country='us', page_size=15)
        else:
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

    while len(stories) < count:
        next_id = len(stories) + 1
        stories.append({
            'id': next_id,
            'title': "More Content Coming Soon", 
            'source': "System",
            'url': "#",
            'description': "Waiting for more headlines to populate."
        })
    return stories

def generate_memory_palace_concept(stories, count):
    wait_for_api_cooldown()
    print("  Designing a Unique Sketchy-Style World (Logic AI)...")
    
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])

    # TWEAKED PROMPT: Added instruction for "Wildly Different" settings
    prompt = f"""
    You are a master of the Method of Loci and a medical mnemonic illustrator.
    
    TASK:
    1. Invent a HIGH-CONCEPT UNIQUE THEME/SETTING for today's news. 
       CRITICAL: Avoid generic parks or offices. Choose something EXOTIC (e.g., 'A Cyberpunk Night Market', 'A 17th Century Pirate Ship', 'A Surreal Candyland', 'A Space Station Greenhouse', 'A Mayan Jungle Temple', 'An Arctic Research Base').
    
    2. For these {count} headlines:
    {story_text}

    3. For EACH story, invent a **Literal Visual Pun** or **Absurd Character**.
       - RULE 1: Everything must be grounded (sitting, standing, or held). 
       - RULE 2: Use "Sketchy Medical" style logic—surreal, funny, and highly visual.
    
    Return JSON format only:
    {{
        "theme_name": "Title of the Scene",
        "setting_description": "Detailed description of the architecture, era, lighting, and atmosphere.",
        "story_elements": [
            {{ 
                "id": 1, 
                "visual_cue": "A giant lobster wearing a crown", 
                "mnemonic_explanation": "Lobster represents the Maine election results; Crown represents the victory.",
                "assigned_zone": "Foreground Left" 
            }}
        ]
    }}
    """
    
    try:
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(clean_json_text(response.text))
    except Exception as e:
        print(f"  Concept Gen Error: {e}")
        return None

def generate_image(scene_concept, count):
    wait_for_api_cooldown()
    
    # Use .get() to prevent KeyError if the AI missed a field
    theme = scene_concept.get('theme_name', 'Daily NewsMap')
    setting = scene_concept.get('setting_description', 'A detailed environment')
    
    print(f"  Drawing the NewsMap: {theme} (Image AI)...")
    
    # 1. World-Building Context
    visual_prompt = f"A SINGLE UNIFIED SCENE set in: {setting}.\n"
    visual_prompt += f"THEME: This is a {theme} themed environment.\n"
    
    # 2. Sketchy Style Keywords
    visual_prompt += (
        "STYLE: Professional educational mnemonic illustration, 'Sketchy Medical' style. "
        "Characterized by vibrant digital art, clean black ink outlines, bold saturated colors, "
        "and flat cell-shading. Perspective: Isometric wide-angle.\n"
    )
    
    # 3. Framing
    visual_prompt += "Format: 4:3 Landscape aspect ratio. Lighting must be consistent with the setting.\n"
    
    # 4. Integrated Objects
    visual_prompt += f"\nINTEGRATE THESE {count} SYMBOLIC OBJECTS NATURALLY INTO THE SCENE:\n"
    elements = scene_concept.get('story_elements', [])
    for element in elements:
        cue = element.get('visual_cue', 'A mystery object')
        zone = element.get('assigned_zone', 'center')
        visual_prompt += f"- In the {zone}: {cue} (Grounded, NO TEXT).\n"
    
    # 5. Negative Prompting (Directly in text)
    visual_prompt += (
        "\nIMPORTANT RULES:\n"
        "- NO text, NO words, NO labels, NO signage.\n"
        "- NO white backgrounds; a fully realized environment only.\n"
        "- Everything must be grounded. NO floating items.\n"
        "- ONE unified scene, not a grid or collage."
    )

    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash-image', 
            contents=visual_prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                return Image.open(BytesIO(part.inline_data.data))
        return None
    except Exception as e:
        print(f"  Image Gen Error: {e}")
        return None

def find_coordinates(image, scene_concept):
    wait_for_api_cooldown()
    print("  Locating mnemonics (Vision AI)...")
    items_to_find = []
    for elem in scene_concept.get('story_elements', []):
        items_to_find.append(f"ID {elem['id']}: {elem['visual_cue']} (Zone: {elem['assigned_zone']})")
    
    items_str = "\n".join(items_to_find)

    prompt = f"""
    Look at this illustration. Find the (x, y) coordinates for the CENTER of each object.
    List:
    {items_str}
    
    Return JSON only:
    {{ "locations": [ {{ "id": 1, "x": 10, "y": 20 }}, ... ] }}
    X and Y must be percentages (0-100).
    """

    try:
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=[prompt, image],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(clean_json_text(response.text))
        return data.get('locations', [])
    except Exception as e:
        print(f"  Vision Analysis Error: {e}")
        return []

def generate_html(section_config, stories, locations, image_filename, theme_name):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NewsMap</title>  <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ background: #f0f4f8; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; margin: 0; padding: 20px 0; }}
            .canvas-container {{ position: relative; width: 95%; max-width: 1100px; border: 5px solid #2d3748; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
            .main-image {{ width: 100%; height: auto; display: block; }}
            .news-marker {{ 
                position: absolute; width: 28px; height: 28px; 
                background: rgba(66, 153, 225, 0.8); backdrop-filter: blur(2px);
                border: 2px solid white; border-radius: 50%; color: white;
                display: flex; justify-content: center; align-items: center;
                font-weight: bold; cursor: pointer; transform: translate(-50%, -50%);
                transition: 0.2s; z-index: 10;
            }}
            .news-marker:hover, .news-marker.active {{ background: #2b6cb0; transform: translate(-50%, -50%) scale(1.3); z-index: 20; }}
            
            .story-card {{
                position: fixed; bottom: -100%; left: 0; right: 0;
                background: white; padding: 25px; border-radius: 20px 20px 0 0;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.3); transition: 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                z-index: 1000; max-width: 600px; margin: 0 auto;
            }}
            .story-card.active {{ bottom: 0; }}
            .overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: none; z-index: 900; }}
            .overlay.active {{ display: block; }}
            .mnemonic-box {{ background: #ebf8ff; border-left: 5px solid #4299e1; padding: 12px; margin: 15px 0; font-style: italic; color: #2c5282; }}
            .read-btn {{ display: block; background: #4299e1; color: white; text-align: center; padding: 15px; border-radius: 10px; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1 style="color: #2d3748; text-align: center; padding: 0 20px;">🗺️ {theme_name}</h1>
        <div class="canvas-container">
            <img src="images/{image_filename}" class="main-image">
    """

    for story in stories:
        loc = next((l for l in locations if l['id'] == story['id']), {'x': 50, 'y': 50})
        html += f'<div class="news-marker" onclick="openStory({story["id"]})" id="marker-{story["id"]}" style="top: {loc["y"]}%; left: {loc["x"]}%;">{story["id"]}</div>'
    
    html += '</div><div class="overlay" onclick="closeAll()"></div>'
    
    for story in stories:
        html += f"""
            <div class="story-card" id="card-{story['id']}">
                <div style="display:flex; justify-content:space-between;">
                    <strong style="color:#4299e1;">{story['source']}</strong>
                    <button onclick="closeAll()" style="border:none; background:none; font-size:24px; cursor:pointer;">&times;</button>
                </div>
                <h3>{story['title']}</h3>
                <div class="mnemonic-box">🧠 Hook: {story.get('mnemonic_explanation', '')}</div>
                <p>{story['description']}</p>
                <a href="{story['url']}" target="_blank" class="read-btn">Full Article</a>
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
    with open(section_config['filename'], 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    print("Starting NewsMap Sketchy Generation...")
    for section in SECTIONS:
        stories = fetch_stories(section['category'], section['story_count'])
        if not stories: continue
            
        concept = generate_memory_palace_concept(stories, section['story_count'])
        if not concept: continue
        
        # Merge mnemonics
        for story in stories:
            for elem in concept.get('story_elements', []):
                if elem['id'] == story['id']:
                    story['mnemonic_explanation'] = elem.get('mnemonic_explanation', '')
        
        image = generate_image(concept, section['story_count'])
        if not image: continue
        
        image_filename = f"{section['filename'].replace('.html', '.png')}"
        image.save(images_dir / image_filename)
        
        locations = find_coordinates(image, concept)
        
        # Use .get() for the final HTML title to prevent any potential KeyErrors
        safe_theme_name = concept.get('theme_name', 'Daily NewsMap')
        generate_html(section, stories, locations, image_filename, safe_theme_name)
        
        try:
            os.system('git add .')
            os.system(f'git commit -m "Auto Update: {safe_theme_name}"')
            os.system('git push origin main')
        except:
            print("Git Push Failed.")
        
    print("\nGeneration Complete!")

if __name__ == "__main__":
    main()