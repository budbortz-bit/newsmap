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
        "story_count": 10,
        "theme": "A busy contemporary City Park on a sunny day. Wide open green spaces, detailed, organic, lively."
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
    """Fetch stories from NewsAPI"""
    stories = []
    print(f"  Fetching {count} stories for category: {category if category else 'General'}...")
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

def generate_memory_palace_concept(stories, theme, count):
    wait_for_api_cooldown()
    print("  Designing the NewsMap (Text AI)...")
    
    story_text = "\n".join([f"Story {s['id']}: {s['title']}" for s in stories])
    zones = [
        "Foreground Left", "Foreground Center", "Foreground Right",
        "Midground Far Left", "Midground Left", "Midground Right", "Midground Far Right",
        "Background Left", "Background Center", "Background Right"
    ]

    prompt = f"""
    Here are exactly {count} headlines:
    {story_text}

    Create a "Memory Palace" scene. Theme: {theme}
    
    Task:
    1. Invent a cohesive setting based on the theme.
    2. For EACH story, invent a **Visual Mnemonic Symbol**.
       - **RULE 1 (Grounding)**: The object must sit on something or be held. NO floating.
       - **RULE 2 (Connection)**: Use PUNS, SOUND-ALIKES, or LITERAL VISUALS.
    3. Provide a short "mnemonic_explanation".

    Return JSON format only:
    {{
        "setting_description": "A detailed description of the setting...",
        "story_elements": [
            {{ 
                "id": 1, 
                "visual_cue": "A large Bull sleeping on a park bench", 
                "mnemonic_explanation": "Bull represents the Bull Market; Sleeping suggests the market is dormant.",
                "assigned_zone": "Foreground Left" 
            }},
            ...
        ]
    }}
    """
    
    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(clean_json_text(response.text))
        return data
    except Exception as e:
        print(f"  Concept Gen Error: {e}")
        return None

def generate_image(scene_concept, count):
    wait_for_api_cooldown()
    print("  Drawing the NewsMap (Image AI)...")
    
    visual_prompt = f"A high-quality, FULL COLOR digital illustration of a SINGLE, UNIFIED SCENE. \n"
    visual_prompt += f"Format: Standard 4:3 Landscape aspect ratio (TV format). \n"
    visual_prompt += f"Style: Educational medical illustration style (like a biology textbook or 'Sketchy Medical'). \n"
    visual_prompt += f"Colors: VIVID, HIGH SATURATION, FULL COLOR. \n"
    visual_prompt += f"NEGATIVE PROMPT: NO floating objects, NO hovering items, NO text, NO words, NO letters, NO numbers, NO labels, NO signage, NO writing. NO comic book panels, NO grid, NO collage. \n\n"
    visual_prompt += f"Setting: {scene_concept['setting_description']}\n\n"
    visual_prompt += f"Integrate these {count} distinct objects seamlessly into the scene:\n"
    for element in scene_concept['story_elements']:
        visual_prompt += f"- Located in the {element['assigned_zone']}: {element['visual_cue']} (Integrated into the environment, NO TEXT)\n"
    visual_prompt += "\nEnsure all objects are grounded (resting on surfaces or held by characters). Consistent lighting."

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
    for elem in scene_concept['story_elements']:
        items_to_find.append(f"ID {elem['id']}: {elem['visual_cue']} (Look in: {elem['assigned_zone']})")
    
    items_str = "\n".join(items_to_find)

    prompt = f"""
    Look at this illustration. Find the location of specific objects.
    I have provided HINTS for where each object is located.
    List:
    {items_str}
    For EACH ID:
    1. Locate the object.
    2. Return the (x, y) coordinates of the CENTER of that object.
    3. Calculate x and y as PERCENTAGES (0 to 100) from the top-left corner.
    Return JSON only:
    {{ "locations": [ {{ "id": 1, "x": 10, "y": 20 }}, ... ] }}
    """

    try:
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[prompt, image],
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(clean_json_text(response.text))
        return data['locations']
    except Exception as e:
        print(f"  Vision Analysis Error: {e}")
        return []

def generate_html(section_config, stories, locations, image_filename):
    """Generate HTML: Unified Ghost Style (Translucent by default)"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>NewsMap: {section_config['name']}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <style>
            body {{ background: #f0f4f8; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px 0; margin: 0; }}
            h1 {{ color: #2d3748; margin-bottom: 20px; font-size: 24px; text-align: center; padding: 0 10px; }}
            
            .canvas-container {{ 
                position: relative; 
                width: 100%; 
                max-width: 1200px; 
                border: 4px solid #2b6cb0; 
                border-radius: 12px; 
                box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
                background: white; 
                overflow: hidden; 
                margin-bottom: 100px; 
            }}
            
            .main-image {{ width: 100%; height: auto; display: block; }}
            
            /* GLOBAL GHOST MARKER STYLE (Base for Desktop & Mobile) */
            .news-marker {{ 
                position: absolute; 
                width: 26px; height: 26px; /* Default Desktop Size */
                
                /* The Ghost Effect */
                background: rgba(66, 153, 225, 0.55); /* See-through Blue */
                backdrop-filter: blur(3px);            /* Frosted Glass */
                border: 1px solid rgba(255, 255, 255, 0.85); 
                
                border-radius: 50%; 
                cursor: pointer; 
                transform: translate(-50%, -50%); 
                z-index: 10; 
                display: flex; justify-content: center; align-items: center;
                color: white; font-weight: bold; font-size: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }}
            
            /* HOVER / ACTIVE STATE (Becomes Solid & Large) */
            .news-marker:hover, .news-marker.active {{ 
                transform: translate(-50%, -50%) scale(1.5); 
                background: #2b6cb0;  /* Solid Blue */
                opacity: 1;
                z-index: 20; 
                border: 2px solid white;
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }}

            /* MOBILE TWEAKS (Just slightly smaller) */
            @media (max-width: 768px) {{
                .news-marker {{ 
                    width: 20px; height: 20px; 
                    font-size: 10px; 
                }}
            }}

            /* MODAL / BOTTOM SHEET */
            .story-card {{
                position: fixed;
                bottom: -100%;
                left: 0; right: 0;
                background: white;
                padding: 20px;
                border-radius: 20px 20px 0 0;
                box-shadow: 0 -10px 40px rgba(0,0,0,0.2);
                transition: bottom 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                z-index: 1000;
                max-width: 600px;
                margin: 0 auto;
            }}

            .story-card.active {{ bottom: 0; }}
            
            .overlay {{
                position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.3);
                z-index: 900;
                display: none;
            }}
            .overlay.active {{ display: block; }}

            .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px; }}
            .story-tag {{ background: #bee3f8; color: #2b6cb0; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
            .close-btn {{ background: none; border: none; font-size: 24px; color: #a0aec0; cursor: pointer; padding: 0; line-height: 1; }}
            
            h3 {{ margin: 0 0 10px 0; font-size: 18px; color: #2d3748; line-height: 1.3; }}
            .mnemonic-box {{ background: #ebf8ff; border-left: 4px solid #4299e1; padding: 10px; margin-bottom: 12px; font-size: 13px; color: #2c5282; font-style: italic; }}
            p {{ margin: 0 0 15px 0; font-size: 14px; line-height: 1.6; color: #4a5568; }}
            .read-btn {{ display: block; width: 100%; background: #4299e1; color: white; text-align: center; padding: 12px 0; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px; box-sizing: border-box; }}
            .read-btn:hover {{ background: #3182ce; }}

            @media (min-width: 769px) {{
                .story-card {{
                    bottom: 20px; left: 50%; transform: translateX(-50%);
                    width: 400px;
                    border-radius: 12px;
                    margin-bottom: -100%;
                }}
                .story-card.active {{ margin-bottom: 0; bottom: 40px; }}
            }}
        </style>
    </head>
    <body>
        <h1>🗺️ NewsMap: Front Page</h1>
        <div class="canvas-container">
            <img src="images/{image_filename}" class="main-image">
    """

    for story in stories:
        loc = next((l for l in locations if l['id'] == story['id']), {'x': 50, 'y': 50})
        html += f"""
            <div class="news-marker" onclick="openStory({story['id']})" id="marker-{story['id']}" style="top: {loc['y']}%; left: {loc['x']}%;">
                {story['id']}
            </div>
        """
    html += "</div>" # End canvas-container

    html += '<div class="overlay" onclick="closeAll()"></div>'
    
    for story in stories:
        mnemonic_text = story.get('mnemonic_explanation', 'Visual mnemonic for this story.')
        html += f"""
            <div class="story-card" id="card-{story['id']}">
                <div class="card-header">
                    <span class="story-tag">{story['source']}</span>
                    <button class="close-btn" onclick="closeAll()">&times;</button>
                </div>
                <h3>{story['title']}</h3>
                <div class="mnemonic-box">🧠 <strong>Hook:</strong> {mnemonic_text}</div>
                <p>{story['description'][:140]}...</p>
                <a href="{story['url']}" target="_blank" class="read-btn">Read Full Story</a>
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
                const cards = document.querySelectorAll('.story-card');
                const markers = document.querySelectorAll('.news-marker');
                const overlay = document.querySelector('.overlay');
                
                cards.forEach(c => c.classList.remove('active'));
                markers.forEach(m => m.classList.remove('active'));
                overlay.classList.remove('active');
            }
        </script>
    </body>
    </html>
    """

    with open(section_config['filename'], 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  Generated {section_config['filename']} successfully!")

def main():
    print("Starting NewsMap Site Generation...")
    
    for section in SECTIONS:
        print(f"\n--- PROCESSING SECTION: {section['name']} ---")
        
        stories = fetch_stories(section['category'], section['story_count'])
        if not stories: continue
            
        concept = generate_memory_palace_concept(stories, section['theme'], section['story_count'])
        if not concept: continue
        
        for story in stories:
            for elem in concept['story_elements']:
                if elem['id'] == story['id']:
                    story['mnemonic_explanation'] = elem.get('mnemonic_explanation', '')
                    break
        
        image = generate_image(concept, section['story_count'])
        if not image: continue
        
        image_filename = f"{section['filename'].replace('.html', '.png')}"
        image_path = images_dir / image_filename
        image.save(image_path, "PNG")
        
        locations = find_coordinates(image, concept)
        generate_html(section, stories, locations, image_filename)
    
    print("\nNewsMap generated! Open index.html to browse.")

if __name__ == "__main__":
    main()