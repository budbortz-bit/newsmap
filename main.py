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
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
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
    print("  Scouting Locations & Designing the World (Logic AI)...")
    
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])

    prompt = f"""
    You are a Cinematic Location Scout and Mnemonic Artist.
    
    TASK:
    1. ANALYZE the headlines for Geographic or Narrative hooks:
    {story_text}

    2. CHOOSE THE SETTING:
       - OPTION A (International): If any headline is international, pick that country's most visually iconic setting.
       - OPTION B (Cinematic): If domestic, pick the most EPIC MOVIE SCENE environment (e.g. Space Station, Western Desert, Cyberpunk City).
    
    3. THE MNEMONICS: For EACH story, invent a Literal Visual Pun or Absurd Character.
       - IMPORTANT: Describe the object CLEARLY (e.g., 'A giant gold trophy', not just 'success').
       - ASSIGN ZONES: Spread them out (Foreground Left, Center, Top Right, etc.).

    Return JSON format only:
    {{
        "chosen_location": "Location Name",
        "theme_name": "Title",
        "setting_description": "Detailed visual setting.",
        "story_elements": [
            {{ 
                "id": 1, 
                "visual_cue": "Specific detailed object description", 
                "mnemonic_explanation": "Link to headline",
                "assigned_zone": "Specific Zone" 
            }}
        ]
    }}
    """
    
    try:
        response = genai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=1.0)
        )
        data = json.loads(clean_json_text(response.text))
        if isinstance(data, list): data = data[0]
        return data
    except Exception as e:
        print(f"  Concept Gen Error: {e}")
        return None

def generate_image(scene_concept, count):
    wait_for_api_cooldown()
    theme = scene_concept.get('theme_name', 'Daily NewsMap')
    setting = scene_concept.get('setting_description', 'A cinematic world')
    
    print(f"  Painting the Scene: {theme} (Image AI)...")
    
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
    print("  Locating mnemonics (Vision AI)...")
    
    # We ask the Vision AI to specifically find the visual_cues we just generated
    items_to_find = [f"ID {e['id']}: {e['visual_cue']}" for e in scene_concept.get('story_elements', [])]
    items_str = "\n".join(items_to_find)

    prompt = f"""
    Look at this illustration. Find the exact (x, y) coordinates for the center of each specific object listed below.
    Be precise. If an object is not found, estimate its location based on the 'assigned_zone' from the concept.
    
    List to find:
    {items_str}
    
    Return JSON format only:
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
        if isinstance(data, list): data = data[0]
        return data.get('locations', [])
    except Exception as e:
        print(f"  Vision Error: {e}")
        return []

def generate_html(section_config, stories, locations, image_filename, theme_name):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NewsMap</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ background: #f0f4f8; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; margin: 0; padding: 20px 0; }}
            .canvas-container {{ position: relative; width: 95%; max-width: 1100px; border: 5px solid #2d3748; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }}
            .main-image {{ width: 100%; height: auto; display: block; }}
            
            .news-marker {{ 
                position: absolute; width: 34px; height: 34px; 
                background: rgba(66, 153, 225, 0.45); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
                border: 2px solid rgba(255, 255, 255, 0.9); border-radius: 50%; color: white;
                display: flex; justify-content: center; align-items: center; font-weight: bold; 
                cursor: pointer; transform: translate(-50%, -50%); transition: 0.2s; z-index: 100;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
            }}
            .news-marker:hover, .news-marker.active {{ background: rgba(43, 108, 176, 0.9); transform: translate(-50%, -50%) scale(1.3); z-index: 200; border-color: white; }}

            @media (max-width: 600px) {{
                .news-marker {{ width: 26px; height: 26px; font-size: 12px; }}
                h1 {{ font-size: 1.4rem; padding: 0 15px; }}
            }}
            
            .story-card {{
                position: fixed; bottom: -100%; left: 0; right: 0; background: white; padding: 25px; border-radius: 25px 25px 0 0;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.4); transition: 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                z-index: 1000; max-width: 600px; margin: 0 auto;
            }}
            .story-card.active {{ bottom: 0; }}
            .overlay {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: none; z-index: 900; }}
            .overlay.active {{ display: block; }}
            .mnemonic-box {{ background: #ebf8ff; border-left: 5px solid #4299e1; padding: 15px; margin: 15px 0; font-style: italic; color: #2c5282; }}
            .read-btn {{ display: block; background: #4299e1; color: white; text-align: center; padding: 16px; border-radius: 12px; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1 style="color: #2d3748; margin-bottom: 20px;">🗺️ {theme_name}</h1>
        <div class="canvas-container">
            <img src="images/{image_filename}" class="main-image">
    """

    for story in stories:
        # Find location or default to a spread-out pattern
        loc = next((l for l in locations if l['id'] == story['id']), {'x': 10 * story['id'], 'y': 50})
        html += f'<div class="news-marker" onclick="openStory({story["id"]})" id="marker-{story["id"]}" style="top: {loc["y"]}%; left: {loc["x"]}%;">{story["id"]}</div>'
    
    html += '</div><div class="overlay" onclick="closeAll()"></div>'
    
    for story in stories:
        html += f"""
            <div class="story-card" id="card-{story['id']}">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <strong style="color:#4299e1; text-transform:uppercase; font-size:12px;">{story['source']}</strong>
                    <button onclick="closeAll()" style="border:none; background:#f0f4f8; border-radius:50%; width:30px; height:30px; cursor:pointer;">&times;</button>
                </div>
                <h3 style="margin-top:0;">{story['title']}</h3>
                <div class="mnemonic-box">🧠 <strong>Hook:</strong> {story.get('mnemonic_explanation', 'Visualizing the news.')}</div>
                <p>{story['description']}</p>
                <a href="{story['url']}" target="_blank" class="read-btn">Read Full Article</a>
                <div style="height:20px;"></div>
            </div>
        """

    html += """
        <script>
            function openStory(id) {
                closeAll();
                document.getElementById('card-' + id).classList.add('active');
                document.getElementById('marker-' + id).classList.add('active');
                document.querySelector('.overlay').classList.add('active');
                document.body.style.overflow = 'hidden';
            }
            function closeAll() {
                document.querySelectorAll('.story-card').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('.news-marker').forEach(m => m.classList.remove('active'));
                document.querySelector('.overlay').classList.remove('active');
                document.body.style.overflow = 'auto';
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
        
        for story in stories:
            for elem in concept.get('story_elements', []):
                if elem['id'] == story['id']:
                    story['mnemonic_explanation'] = elem.get('mnemonic_explanation', '')
        
        image = generate_image(concept, section['story_count'])
        if not image: continue
        
        image_filename = f"{section['filename'].replace('.html', '.png')}"
        image.save(images_dir / image_filename)
        
        locations = find_coordinates(image, concept)
        generate_html(section, stories, locations, image_filename, concept.get('theme_name', 'Daily NewsMap'))
        
        try:
            os.system('git add .')
            os.system(f'git commit -m "Automated Scout Update"')
            os.system('git push origin main')
        except:
            print("Git Push Failed.")
        
    print("\nGeneration Complete!")

if __name__ == "__main__":
    main()