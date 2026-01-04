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
    
    # 1. READ THE PREVIOUS THEME
    previous_theme = "None"
    if os.path.exists('last_theme.txt'):
        with open('last_theme.txt', 'r') as f:
            previous_theme = f.read().strip()

    print(f"  Scouting Locations (Avoiding: {previous_theme})...")
    
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])

    prompt = f"""
    You are a Cinematic Location Scout and Mnemonic Artist.
    
    TASK:
    1. ANALYZE the headlines for Geographic or Narrative hooks:
    {story_text}

    2. CHOOSE THE SETTING:
       - OPTION A (International): If any headline is international, pick that country's most visually iconic setting.
       - OPTION B (Cinematic): If domestic, pick the most EPIC MOVIE SCENE environment.
    
    3. CRITICAL VARIETY RULE:
       - DO NOT use the theme: '{previous_theme}'. 
       - You must pick something visually and geographically distinct from the previous run to ensure variety.
    
    4. THE MNEMONICS: For EACH of the {count} stories, invent a unique Literal Visual Pun.
       - RULE: Describe objects clearly and assign distinct zones (Top Left, Center, etc.).

    Return JSON format only:
    {{
        "chosen_location": "Name of the location",
        "theme_name": "Internal Theme Title",
        "setting_description": "Vivid description...",
        "story_elements": [...]
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
        
        # 2. SAVE THE NEW THEME FOR NEXT TIME
        new_location = data.get('chosen_location', 'Dynamic Setting')
        with open('last_theme.txt', 'w') as f:
            f.write(new_location)
            
        print(f"  Location Scout: {new_location}")
        return data
    except Exception as e:
        print(f"  Concept Gen Error: {e}")
        return None

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
    print("  Locating mnemonics (Vision AI)...")
    
    # SAFE EXTRACTION: Use .get() and filters to prevent KeyError
    story_elements = scene_concept.get('story_elements', [])
    items_to_find = []
    
    for e in story_elements:
        # Check for 'id' safely; skip if missing
        eid = e.get('id')
        cue = e.get('visual_cue', 'object')
        if eid is not None:
            items_to_find.append(f"ID {eid}: {cue}")
    
    if not items_to_find:
        print("  Vision Error: No valid story elements found to locate.")
        return []

    items_str = "\n".join(items_to_find)

    prompt = f"""
    Look at this illustration. Find the exact (x, y) coordinates for the center of each specific object listed below.
    Precise mapping is required. If you cannot find an object, estimate its location based on the scene.
    
    List:
    {items_str}
    
    Return JSON format only:
    {{ "locations": [ {{ "id": 1, "x": 10, "y": 20 }}, ... ] }}
    X and Y are percentages (0-100).
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
        # 1. Fetch news headlines
        stories = fetch_stories(section['category'], section['story_count'])
        if not stories: 
            print(f"  No stories found for {section['name']}. Skipping.")
            continue
        
        # 2. Design the world concept (Memory Palace)
        concept = generate_memory_palace_concept(stories, section['story_count'])
        if not concept: 
            print(f"  Failed to generate concept. Skipping.")
            continue
        
        # 3. Match mnemonics to stories (Resilient to KeyErrors)
        story_elements = concept.get('story_elements', [])
        for story in stories:
            # We look through the AI's elements to find the matching ID
            for elem in story_elements:
                # Use .get() to avoid crashing if 'id' is missing from AI response
                if elem.get('id') == story.get('id'):
                    story['mnemonic_explanation'] = elem.get('mnemonic_explanation', 'Visualized in scene.')
                    break # Found the match, move to next story

        # 4. Generate the illustration
        image = generate_image(concept, section['story_count'])
        if not image: 
            print(f"  Failed to generate image. Skipping.")
            continue

        # 5. Define UNIQUE FILENAMES
        # e.g., 2026-01-04_17-50-20_Front_Page.png
        base_name = f"{run_timestamp}_{section['name'].replace(' ', '_')}"
        image_name = f"{base_name}.png"
        html_name = f"{base_name}.html"
        
        # 6. Save the unique image to the images directory
        image.save(images_dir / image_name)
        
        # 7. Locate mnemonics using Vision AI
        locations = find_coordinates(image, concept)
        
        # 8. Generate Archive HTML (Saved in /archives folder)
        # Note: is_archive=True tells the function to look up one level for the images
        generate_html(
            section, 
            stories, 
            locations, 
            image_name, 
            concept.get('theme_name', 'NewsMap'), 
            archives_dir / html_name, 
            is_archive=True
        )
        
        # 9. Update Main index.html (In root folder) for the "latest" view
        generate_html(
            section, 
            stories, 
            locations, 
            image_name, 
            concept.get('theme_name', 'NewsMap'), 
            section['filename'], 
            is_archive=False
        )
        
        # 10. Rebuild the visual gallery grid (gallery.html)
        update_gallery()
        
        # 11. Sync with GitHub
        try:
            print(f"  Syncing {run_timestamp} to GitHub...")
            os.system('git add .')
            # Using double quotes for the commit message to handle spaces safely in Windows/Linux
            os.system(f'git commit -m "Automated Run: {run_timestamp}"')
            os.system('git push origin main')
        except Exception as e: 
            print(f"  Git failed: {e}")

if __name__ == "__main__":
    main()