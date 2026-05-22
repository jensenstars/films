import os
import requests
import json
import re
import sys
from bs4 import BeautifulSoup

API_KEY = os.getenv('TMDB_API_KEY')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
ISSUE_TITLE = os.getenv('ISSUE_TITLE')

print(f"Bot started. Parsing input: '{ISSUE_TITLE}'")

if not API_KEY:
    print("ERROR: TMDB_API_KEY is missing!")
    sys.exit(1)

def slugify(text):
    return re.sub(r'\W+', '-', text.lower()).strip('-')

# --- IMDb Rating Fetch ---
def get_imdb_rating(imdb_id):
    if not imdb_id or not OMDB_API_KEY: return "--"
    try:
        url = f"https://www.omdbapi.com/?apikey={OMDB_API_KEY}&i={imdb_id}"
        res = requests.get(url, timeout=10).json()
        if res.get('Response') == 'True':
            rating = res.get('imdbRating', '--')
            return str(rating) if rating != 'N/A' else "--"
    except Exception as e:
        print(f"OMDb Request failed: {e}")
    return "--"

# --- Letterboxd Scraper ---
def get_letterboxd_rating(imdb_id):
    if not imdb_id or not imdb_id.startswith('tt'): return "--"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        url = f"https://letterboxd.com/imdb/{imdb_id}/"
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'html.parser')
        meta_tag = soup.find('meta', attrs={'name': 'twitter:data2'})
        if meta_tag:
            match = re.search(r'([0-9.]+)\sout\sof', meta_tag['content'])
            if match:
                return str(match.group(1))
    except Exception as e:
        print(f"LB Scraper failed: {e}")
    return "--"

# --- Fetch details helper ---
def fetch_details(query):
    print("Calling TMDB API...")
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={query}"
    search = requests.get(search_url).json()
    
    if not search.get('results'): 
        print(f"ERROR: No movie found for '{query}'.")
        return None
    
    m_id = search['results'][0]['id']
    m = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={API_KEY}&append_to_response=credits").json()
    
    director = next((c['name'] for c in m['credits']['crew'] if c['job'] == 'Director'), "Unknown")
    
    # --- SMART REGION EXTRACTOR ---
    if m.get('production_countries'):
        country_code = m['production_countries'][0]['iso_3166_1'] # "US", "AR", etc.
        country_name = m['production_countries'][0]['name']       # "United States of America", "Argentina", etc.
    else:
        country_code = "Other"
        country_name = "Other"

    # Custom overrides for your preferred specific names
    overrides = {
        "CN": "Mainland China",
        "US": "USA",
        "United States of America": "USA",
        "GB": "United Kingdom"
    }
    
    # Try code override first, then name override, then fall back to TMDB's full English name!
    region = overrides.get(country_code, overrides.get(country_name, country_name))
    print(f"Region parsed: code={country_code}, raw_name={country_name} -> display_as={region}")
    
    imdb_id = m.get('imdb_id')
    print(f"Found IMDb ID: {imdb_id}. Fetching secondary ratings...")

    imdb_score = get_imdb_rating(imdb_id)
    lb_score = get_letterboxd_rating(imdb_id)
    
    return {
        "title": m['title'],
        "original_title": m.get('original_title', m['title']),
        "year": m.get('release_date', 'Unknown')[:4],
        "director": director,
        "region": region, # Using our smart parsed region
        "rating": round(m.get('vote_average', 0), 1),
        "imdb_rating": imdb_score,
        "lb_rating": lb_score,
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "",
        "desc": m.get('overview', 'No description available.'),
        "watch_link": f"https://watchseries.bar/search/{slugify(m['title'])}"
    }

# --- MAIN LOGIC FLOW ---
file_path = 'data/movies.json'

# Detect if this is a REMOVE or DELETE command
target_title = ISSUE_TITLE.strip()
is_removal = False

removal_match = re.match(r'^(remove|delete):\s*(.*)$', target_title, re.IGNORECASE)
if removal_match:
    is_removal = True
    target_title = removal_match.group(2).strip()
    print(f"REMOVAL COMMAND DETECTED for movie: '{target_title}'")

if is_removal:
    # 1. Fetch official TMDB title for deletion to handle typos/variations
    print("Fetching official TMDB title for accurate deletion...")
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={target_title}"
    search = requests.get(search_url).json()
    
    if search.get('results'):
        official_title = search['results'][0]['title']
    else:
        official_title = target_title # Fallback to user text if TMDB offline
        
    print(f"Target title to remove: '{official_title}'")

    # 2. Modify JSON database
    with open(file_path, 'r+') as f:
        try:
            db = json.load(f)
        except:
            db = []
            
        original_count = len(db)
        # Filter out the movie (case-insensitive match)
        db = [m for m in db if m['title'].lower() != official_title.lower()]
        new_count = len(db)
        
        if new_count < original_count:
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
            print(f"SUCCESS: Removed '{official_title}' from the database.")
        else:
            print(f"NOTICE: '{official_title}' was not found in your list. No changes made.")

else:
    # Standard ADD/UPDATE Logic
    movie = fetch_details(target_title)
    if movie:
        print(f"Success! TMDB: {movie['rating']}, IMDb: {movie['imdb_rating']}, LB: {movie['lb_rating']}")
        
        with open(file_path, 'r+') as f:
            try:
                db = json.load(f)
            except:
                db = []
                
            existing_index = next((i for i, m in enumerate(db) if m['title'] == movie['title']), None)
            
            if existing_index is not None:
                print(f"Notice: '{movie['title']}' already exists. Overwriting with fresh ratings & data!")
                db[existing_index] = movie
            else:
                db.append(movie)
                print(f"Successfully added new movie: '{movie['title']}'!")
                
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
    else:
        print("Script finished without finding a movie.")
        
