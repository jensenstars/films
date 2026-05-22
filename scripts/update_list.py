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

# --- Extract Official YouTube Trailer ---
def get_trailer_link(video_data):
    results = video_data.get('results', [])
    # 1. Search for official YouTube Trailer
    trailer = next((v for v in results if v.get('type') == 'Trailer' and v.get('site') == 'YouTube' and v.get('official')), None)
    # 2. Fallback to any YouTube trailer
    if not trailer:
        trailer = next((v for v in results if v.get('type') == 'Trailer' and v.get('site') == 'YouTube'), None)
    # 3. Fallback to any YouTube video clip
    if not trailer:
        trailer = next((v for v in results if v.get('site') == 'YouTube'), None)
        
    if trailer:
        return f"https://www.youtube.com/watch?v={trailer['key']}"
    return ""

# --- Unified Fetch Details ---
def fetch_details(query):
    year_match = re.search(r'\b(19\d\d|20\d\d)\b', query)
    target_year = year_match.group(1) if year_match else None
    
    clean_query = query
    if target_year:
        print(f"Target year constraint parsed: '{target_year}'")
        clean_query = re.sub(r'\(?\b' + target_year + r'\b\)?', '', query)
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()

    print(f"Calling TMDB Multi-Search API for: '{clean_query}'...")
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={API_KEY}&query={clean_query}"
    search = requests.get(search_url).json()
    
    if not search.get('results'): 
        print(f"ERROR: No result found for '{clean_query}'.")
        return None
        
    valid_results = [r for r in search['results'] if r.get('media_type') in ['movie', 'tv']]
    if not valid_results:
        print("ERROR: No valid movie or TV series found.")
        return None
        
    final_result = None
    if target_year:
        for r in valid_results:
            date_str = r.get('release_date') or r.get('first_air_date')
            if date_str and date_str.startswith(target_year):
                final_result = r
                print(f"MATCH FOUND: Found release matching year {target_year}!")
                break
                
    if not final_result:
        final_result = valid_results[0]
        
    media_type = final_result['media_type']
    m_id = final_result['id']
    
    print(f"Selected {media_type.upper()} with ID: {m_id}. Fetching details & videos...")
    
    if media_type == 'movie':
        # Appending videos to TMDB call
        m = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={API_KEY}&append_to_response=credits,videos").json()
        title = m['title']
        original_title = m.get('original_title', title)
        year = m.get('release_date', 'Unknown')[:4]
        director = next((c['name'] for c in m['credits']['crew'] if c['job'] == 'Director'), "Unknown")
        imdb_id = m.get('imdb_id')
        country = m['production_countries'][0]['iso_3166_1'] if m.get('production_countries') else "Other"
        country_name = m['production_countries'][0]['name'] if m.get('production_countries') else "Other"
    else:
        # Appending videos to TV details
        m = requests.get(f"https://api.themoviedb.org/3/tv/{m_id}?api_key={API_KEY}&append_to_response=videos").json()
        title = m['name']
        original_title = m.get('original_name', title)
        year = m.get('first_air_date', 'Unknown')[:4]
        
        creators = m.get('created_by', [])
        director = f"{creators[0]['name']} (Show Creator)" if creators else "Unknown (TV Series)"
        
        ext_ids = requests.get(f"https://api.themoviedb.org/3/tv/{m_id}/external_ids?api_key={API_KEY}").json()
        imdb_id = ext_ids.get('imdb_id')
        
        if m.get('origin_country'):
            country = m['origin_country'][0]
            country_mapper = {"CN": "Mainland China", "HK": "Hong Kong", "TW": "Taiwan", "KR": "South Korea", "JP": "Japan", "US": "United States of America"}
            country_name = country_mapper.get(country, country)
        else:
            country, country_name = "Other", "Other"

    overrides = {
        "CN": "Mainland China",
        "US": "USA",
        "United States of America": "USA",
        "GB": "United Kingdom"
    }
    region = overrides.get(country, overrides.get(country_name, country_name))

    # Fetch ratings & trailer
    imdb_score = get_imdb_rating(imdb_id)
    lb_score = get_letterboxd_rating(imdb_id)
    trailer_url = get_trailer_link(m.get('videos', {}))
    
    return {
        "title": title,
        "original_title": original_title,
        "year": year,
        "director": director,
        "region": region,
        "rating": round(m.get('vote_average', 0), 1),
        "imdb_rating": imdb_score,
        "lb_rating": lb_score,
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "",
        "watch_link": f"https://watchseries.bar/search/{slugify(title)}",
        "trailer_link": trailer_url # Saved trailer link
    }

# --- MAIN LOGIC FLOW ---
file_path = 'data/movies.json'
target_title = ISSUE_TITLE.strip()
is_removal = False

removal_match = re.match(r'^(remove|delete):\s*(.*)$', target_title, re.IGNORECASE)
if removal_match:
    is_removal = True
    target_title = removal_match.group(2).strip()
    print(f"REMOVAL COMMAND DETECTED for movie: '{target_title}'")

if is_removal:
    print("Fetching official TMDB title for accurate deletion...")
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={API_KEY}&query={target_title}"
    search = requests.get(search_url).json()
    
    valid_results = [r for r in search['results'] if r.get('media_type') in ['movie', 'tv']]
    if valid_results:
        first_res = valid_results[0]
        official_title = first_res['title'] if first_res['media_type'] == 'movie' else first_res['name']
    else:
        official_title = target_title
        
    print(f"Target title to remove: '{official_title}'")

    with open(file_path, 'r+') as f:
        try:
            db = json.load(f)
        except:
            db = []
            
        original_count = len(db)
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
    movie = fetch_details(target_title)
    if movie:
        print(f"Success! TMDB: {movie['rating']}, IMDb: {movie['imdb_rating']}, LB: {movie['lb_rating']}, Trailer: {movie['trailer_link']}")
        
        with open(file_path, 'r+') as f:
            try:
                db = json.load(f)
            except:
                db = []
                
            existing_index = next((i for i, m in enumerate(db) if m['title'] == movie['title']), None)
            
            if existing_index is not None:
                print(f"Notice: '{movie['title']}' already exists. Overwriting with updated data!")
                db[existing_index] = movie
            else:
                db.append(movie)
                print(f"Successfully added: '{movie['title']}'!")
                
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
    else:
        print("Script finished without finding a movie.")
