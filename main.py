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

# --- CONFIGURATION (SINGLE PAGE) ---
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

    # Safety Pad
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

    # UPDATED PROMPT: Enforces "Concrete/Pun" logic and asks for an Explanation
    prompt = f"""
    Here are exactly {count} headlines:
    {story_text}

    Create a "Memory Palace" scene. Theme: {theme}
    
    Task:
    1. Invent a cohesive setting based on the theme.
    2. For EACH story, invent a **Visual Mnemonic Symbol**.
       - **RULE 1 (Grounding)**: The object must sit on something or be held. NO floating.
       - **RULE 2 (Connection)**: Use PUNS, SOUND-ALIKES, or LITERAL VISUALS.
         - Bad: "A scale" for Justice Dept (Too abstract).
         - Good: "A jar of ICE" for an ISIS story (Sound-alike).
         - Good: "A Bull" for a stock market rally (Literal/Iconic).
    3. Provide a short "mnemonic_explanation" for why you chose that symbol.

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
    {{
        "locations": [
            {{ "id": 1, "x": 10, "y": 20 }},
            ...
        ]
    }}
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
    """Generate Single Page HTML with Mnemonic Explanations"""

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
                margin-bottom: 50px; 
                box-sizing: border-box; 
            }}
            
            .main-image {{ width: 100%; height: auto; display: block; }}
            
            /* Markers */
            .news-marker {{ position: absolute; width: 32px; height: 32px; background: rgba(66, 153, 225, 0.85); border: 2px solid #fff; border-radius: 50%; cursor: pointer; transform: translate(-50%, -50%); transition: all 0.2s ease; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
            .news-marker:hover {{ background: #2b6cb0; transform: translate(-50%, -50%) scale(1.2); z-index: 30; border-color: #bee3f8; }}
            .marker-number {{ display: flex; justify-content: center; align-items: center; width: 100%; height: 100%; color: white; font-weight: bold; font-size: 14px; }}
            
            /* --- POPUP LOGIC --- */
            .summary-box {{ position: absolute; width: 300px; background: white; color: #2d3748; padding: 16px; border-radius: 8px; box-shadow: 0 15px 30px rgba(0,0,0,0.25); opacity: 0; visibility: hidden; transition: opacity 0.2s; pointer-events: auto; z-index: 20; text-align: left; border: 1px solid #e2e8f0; }}
            
            /* Positioning Classes (Up/Down/Left/Right) */
            .summary-box.popup-center {{ left: 50%; transform: translateX(-50%); }}
            .summary-box.popup-left {{ left: 0; transform: translateX(0); }}
            .summary-box.popup-right {{ right: 0; left: auto; transform: translateX(0); }}
            
            .summary-box.popup-up {{ bottom: 130%; }}
            .summary-box.popup-up::after {{ content: ""; position: absolute; top: 100%; left: 50%; border: 8px solid transparent; border-top-color: white; margin-left: -8px; }}

            .summary-box.popup-down {{ top: 130%; }}
            .summary-box.popup-down::after {{ content: ""; position: absolute; bottom: 100%; left: 50%; border: 8px solid transparent; border-bottom-color: white; margin-left: -8px; }}

            .news-marker:hover .summary-box, .summary-box:hover {{ opacity: 1; visibility: visible; }}
            
            /* Typography */
            h3 {{ margin: 0 0 6px 0; font-size: 16px; color: #2d3748; line-height: 1.3;}}
            .source {{ font-size: 11px; color: #718096; text-transform: uppercase; font-weight: 700; margin-bottom: 8px; display: block;}}
            p {{ margin: 0 0 10px 0; font-size: 13px; line-height: 1.5; color: #4a5568;}}
            .mnemonic-hint {{ background: #ebf8ff; color: #2c5282; padding: 8px; border-radius: 4px; font-size: 12px; font-style: italic; margin-bottom: 10px; border-left: 3px solid #4299e1; }}
            a {{ display: inline-block; background: #4299e1; color: white; padding: 4px 12px; border-radius: 4px; text-decoration: none; font-size: 12px; font-weight: 600; }}

            /* Mobile Overrides */
            @media (max-width: 768px) {{
                .canvas-container {{ border: none; border-radius: 0; margin-bottom: 20px; }}
                .news-marker {{ width: 40px; height: 40px; }}
                .summary-box, .summary-box.popup-up, .summary-box.popup-down, .summary-box.popup-left, .summary-box.popup-right {{
                    position: fixed !important; bottom: 0 !important; top: auto !important; left: 0 !important; right: 0 !important;
                    width: 100% !important; max-width: 100% !important; transform: none !important;
                    border-radius: 16px 16px 0 0; box-shadow: 0 -5px 20px rgba(0,0,0,0.2); margin: 0 !important; z-index: 9999;
                }}
                .summary-box::after {{ display: none !important; }}
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
        x_pos = float(loc['x'])
        y_pos = float(loc['y'])
        
        # Calculate Desktop Classes
        v_class = "popup-down" if y_pos < 40 else "popup-up"
        if x_pos < 20: h_class = "popup-left"
        elif x_pos > 80: h_class = "popup-right"
        else: h_class = "popup-center"
        
        # Fallback if mnemonic connection is missing
        mnemonic_text = story.get('mnemonic_explanation', 'Visual mnemonic for this story.')

        html += f"""
            <div class="news-marker" style="top: {loc['y']}%; left: {loc['x']}%;">
                <div class="marker-number">{story['id']}</div>
                <div class="summary-box {v_class} {h_class}">
                    <h3>{story['title']}</h3>
                    <span class="source">{story['source']}</span>
                    <div class="mnemonic-hint">🧠 <strong>Memory Hook:</strong> {mnemonic_text}</div>
                    <p>{story['description'][:140]}...</p>
                    <a href="{story['url']}" target="_blank">Read Story</a>
                </div>
            </div>
        """

    html += """
        </div>
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
        if not stories: 
            print("  Skipping section due to API error.")
            continue
            
        concept = generate_memory_palace_concept(stories, section['theme'], section['story_count'])
        if not concept: continue
        
        # CRITICAL STEP: Merge Mnemonic Explanations back into Story List
        # This connects the "Reasoning" from the Text AI to the "Popup" in the HTML
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
        print(f"  Saved image: {image_filename}")
        
        locations = find_coordinates(image, concept)
        generate_html(section, stories, locations, image_filename)
    
    print("\nNewsMap generated! Open index.html to browse.")

if __name__ == "__main__":
    main()