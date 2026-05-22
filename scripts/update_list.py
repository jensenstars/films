import os
import requests
import json
import re
import sys

API_KEY = os.getenv('TMDB_API_KEY')
ISSUE_TITLE = os.getenv('ISSUE_TITLE')

print(f"Bot started. Searching for: '{ISSUE_TITLE}'")

if not API_KEY:
    print("ERROR: TMDB_API_KEY is missing! Check your GitHub Secrets.")
    sys.exit(1)

def slugify(text):
    return re.sub(r'\W+', '-', text.lower()).strip('-')

def fetch_details(query):
    print("Calling TMDB API...")
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={query}"
    search = requests.get(search_url).json()
    
    if not search.get('results'): 
        print(f"ERROR: No movie found on TMDB for '{query}'. Try just the movie name without the year.")
        return None
    
    m_id = search['results'][0]['id']
    print(f"Found movie ID: {m_id}. Fetching details...")
    
    m = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={API_KEY}&append_to_response=credits").json()
    
    director = next((c['name'] for c in m['credits']['crew'] if c['job'] == 'Director'), "Unknown")
    
    country = m['production_countries'][0]['iso_3166_1'] if m.get('production_countries') else "Other"
    regions = {"CN": "Mainland China", "HK": "Hong Kong", "TW": "Taiwan", "FR": "France", "US": "USA", "JP": "Japan", "KR": "South Korea"}
    
    return {
        "title": m['title'],
        "original_title": m.get('original_title', m['title']),
        "year": m.get('release_date', 'Unknown')[:4],
        "director": director,
        "region": regions.get(country, country),
        "rating": round(m.get('vote_average', 0), 1),
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "",
        "desc": m.get('overview', 'No description available.'),
        "watch_link": f"https://watchseries.bar/search/{slugify(m['title'])}"
    }

movie = fetch_details(ISSUE_TITLE)

if movie:
    print(f"Success! Fetched data for: {movie['title']}")
    file_path = 'data/movies.json'
    
    if not os.path.exists(file_path):
        print(f"ERROR: {file_path} does not exist in your repository. Please create it.")
        sys.exit(1)
        
    with open(file_path, 'r+') as f:
        try:
            db = json.load(f)
        except json.JSONDecodeError:
            print("Warning: movies.json was empty or invalid. Starting fresh array.")
            db = []
            
        # Optional: check for duplicates before adding
        if any(m['title'] == movie['title'] for m in db):
            print(f"Notice: '{movie['title']}' is already in the list. Skipping.")
        else:
            db.append(movie)
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
            print("Successfully saved to data/movies.json!")
else:
    print("Script finished without finding a movie.")
