import os
import requests
import json
import re

TMDB_API_KEY = os.getenv('TMDB_API_KEY')
ISSUE_TITLE = os.getenv('ISSUE_TITLE') # Example: "Seven Samurai"

def slugify(text):
    return re.sub(r'\W+', '-', text.lower()).strip('-')

def fetch_movie(query):
    # 1. Search
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}"
    search_data = requests.get(search_url).json()
    if not search_data['results']: return None
    
    movie_id = search_data['results'][0]['id']
    
    # 2. Get Details
    detail_url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
    m = requests.get(detail_url).json()
    
    # 3. Extract Info
    director = next((c['name'] for c in m['credits']['crew'] if c['job'] == 'Director'), "Unknown")
    country_code = m['production_countries'][0]['iso_3166_1'] if m['production_countries'] else "Other"
    
    # Map country codes to Display Names
    countries = {"CN": "Mainland China", "HK": "Hong Kong", "TW": "Taiwan", "JP": "Japan", "FR": "France", "US": "USA", "KR": "South Korea"}
    region = countries.get(country_code, country_code)

    return {
        "title": m['title'],
        "original_title": m.get('original_title', ''),
        "year": m['release_date'][:4],
        "director": director,
        "region": region,
        "rating": round(m['vote_average'], 1),
        "poster": f"https://image.tmdb.org/t/p/w500{m['poster_path']}",
        "desc": m['overview'],
        "watch_link": f"https://watchseries.bar/search/{slugify(m['title'])}"
    }

# Update Logic
new_movie = fetch_movie(ISSUE_TITLE)
if new_movie:
    with open('data/movies.json', 'r+') as f:
        data = json.load(f)
        # Update if exists, else append
        data = [m for m in data if m['title'] != new_movie['title']]
        data.append(new_movie)
        f.seek(0)
        json.dump(data, f, indent=4)
        f.truncate()
