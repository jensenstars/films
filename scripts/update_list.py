import os
import requests
import json
import re

API_KEY = os.getenv('TMDB_API_KEY')
ISSUE_TITLE = os.getenv('ISSUE_TITLE')

def slugify(text):
    return re.sub(r'\W+', '-', text.lower()).strip('-')

def fetch_details(query):
    # Search
    search = requests.get(f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={query}").json()
    if not search['results']: return None
    
    m_id = search['results'][0]['id']
    # Details + Credits
    m = requests.get(f"https://api.themoviedb.org/3/movie/{m_id}?api_key={API_KEY}&append_to_response=credits").json()
    
    director = next((c['name'] for c in m['credits']['crew'] if c['job'] == 'Director'), "Unknown")
    
    # Simple Region Mapping
    country = m['production_countries'][0]['iso_3166_1'] if m['production_countries'] else "Other"
    regions = {"CN": "Mainland China", "HK": "Hong Kong", "TW": "Taiwan", "FR": "France", "US": "USA"}
    
    return {
        "title": m['title'],
        "original_title": m.get('original_title', m['title']),
        "year": m['release_date'][:4],
        "director": director,
        "region": regions.get(country, country),
        "rating": round(m['vote_average'], 1),
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
        "desc": m['overview'],
        "watch_link": f"https://watchseries.bar/search/{slugify(m['title'])}"
    }

movie = fetch_details(ISSUE_TITLE)
if movie:
    with open('data/movies.json', 'r+') as f:
        db = json.load(f)
        db.append(movie)
        f.seek(0)
        json.dump(db, f, indent=2)
        f.truncate()
