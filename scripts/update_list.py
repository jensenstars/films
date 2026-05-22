import os
import requests
import json
import re
import sys
from bs4 import BeautifulSoup

API_KEY = os.getenv('TMDB_API_KEY')
ISSUE_TITLE = os.getenv('ISSUE_TITLE')

print(f"Bot started. Searching for: '{ISSUE_TITLE}'")

if not API_KEY:
    print("ERROR: TMDB_API_KEY is missing! Check your GitHub Secrets.")
    sys.exit(1)

def slugify(text):
    return re.sub(r'\W+', '-', text.lower()).strip('-')

# --- NEW: Grab IMDb Rating ---
def get_imdb_rating(imdb_id):
    if not imdb_id: return "--"
    try:
        res = requests.get(f"https://search.imdbot.workers.dev/?tt={imdb_id}").json()
        return str(res['short']['aggregateRating']['ratingValue'])
    except:
        return "--"

# --- NEW: Grab Letterboxd Rating ---
def get_letterboxd_rating(imdb_id):
    if not imdb_id: return "--"
    try:
        url = f"https://letterboxd.com/imdb/{imdb_id}/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        
        soup = BeautifulSoup(res.text, 'html.parser')
        meta_tag = soup.find('meta', attrs={'name': 'twitter:data2'})
        if meta_tag:
            match = re.search(r'([0-9.]+)\sout\sof', meta_tag['content'])
            if match:
                return str(match.group(1))
        return "--"
    except:
        return "--"

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
    country = m['production_countries'][0]['iso_3166_1'] if m.get('production_countries') else "Other"
    regions = {"CN": "Mainland China", "HK": "Hong Kong", "TW": "Taiwan", "FR": "France", "US": "USA", "JP": "Japan", "KR": "South Korea"}
    
    # 1. Grab TMDB's IMDb ID reference
    imdb_id = m.get('imdb_id')
    print(f"Found IMDb ID: {imdb_id}. Fetching secondary ratings...")

    # 2. Fetch the extra ratings
    imdb_score = get_imdb_rating(imdb_id)
    lb_score = get_letterboxd_rating(imdb_id)
    
    return {
        "title": m['title'],
        "original_title": m.get('original_title', m['title']),
        "year": m.get('release_date', 'Unknown')[:4],
        "director": director,
        "region": regions.get(country, country),
        "rating": round(m.get('vote_average', 0), 1),
        "imdb_rating": imdb_score,
        "lb_rating": lb_score,
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}" if m.get('poster_path') else "",
        "desc": m.get('overview', 'No description available.'),
        "watch_link": f"https://watchseries.bar/search/{slugify(m['title'])}"
    }

movie = fetch_details(ISSUE_TITLE)

if movie:
    print(f"Success! TMDB: {movie['rating']}, IMDb: {movie['imdb_rating']}, LB: {movie['lb_rating']}")
    file_path = 'data/movies.json'
        
    with open(file_path, 'r+') as f:
        try:
            db = json.load(f)
        except:
            db = []
            
        if any(m['title'] == movie['title'] for m in db):
            print(f"Notice: '{movie['title']}' is already in the list. Skipping.")
        else:
            db.append(movie)
            f.seek(0)
            json.dump(db, f, indent=2)
            f.truncate()
            print("Successfully saved new movie with all ratings to data/movies.json!")
else:
    print("Script finished without finding a movie.")
