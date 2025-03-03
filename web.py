from flask import Flask, render_template, request, redirect, url_for
import os
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from typing import List, Dict
import time

load_dotenv()

# Add the directory containing main.py to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import get_band_name_and_songs, create_spotify_playlist

app = Flask(__name__)

# Configure your Spotify app credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
PLAYLIST_ID = None
PLAYLIST_URL = None


@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles the main route for the web application.

    This function processes GET and POST requests to the root URL ("/").
    It handles form submissions, extracts setlist data, creates a Spotify playlist,
    and renders the index.html template with the results.

    Returns:
        str: The rendered HTML content of the index.html template.
    """
    global PLAYLIST_ID, PLAYLIST_URL
    results: List[Dict] = []
    error = None
    playlist_id = PLAYLIST_ID
    playlist_url = PLAYLIST_URL

    if request.method == "POST":
        urls = request.form.getlist("url")  # Get all submitted URLs
        # Spotify Auth
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                                            client_secret=SPOTIPY_CLIENT_SECRET,
                                                            redirect_uri=SPOTIPY_REDIRECT_URI,
                                                            scope="playlist-modify-private"))
        except Exception as e:
            error = str(e)
            return render_template("index.html", results=results, error=error, playlist_id=playlist_id,
                                   playlist_url=playlist_url)

        songs_lists = []
        band_names = []
        for url in urls:
            result = {
                'playlist_url': None,
                'playlist_id': None,
                'band_name': None,
                'location': None,
                'error': None
            }

            try:
                setlist_data = get_band_name_and_songs(url)
                if setlist_data["error"]:
                    result["error"] = setlist_data["error"]
                elif not setlist_data["band_name"] or not setlist_data["songs"]:
                    result["error"] = "Could not extract band name or songs from the URL."
                else:
                    songs_lists.append(setlist_data["songs"])
                    band_name = setlist_data["band_name"]
                    band_names.append(band_name)
                    location = setlist_data["location"]
                    result["band_name"] = band_name
                    result["location"] = location
            except Exception as e:
                result["error"] = str(e)
            results.append(result)

        try:
            playlist_data = create_spotify_playlist(songs_lists, band_names, sp)
            if playlist_data.get("error"):
                error = playlist_data.get("error")
            else:
                PLAYLIST_ID = playlist_data["id"]
                playlist_id = PLAYLIST_ID
                # get playlist url
                playlist_full_info = sp.playlist(playlist_id)
                PLAYLIST_URL = playlist_full_info["external_urls"]["spotify"].replace("https://open.spotify.com/playlist/","https://open.spotify.com/embed/playlist/")
                playlist_url = PLAYLIST_URL
                # Redirect here
                return redirect(url_for('index'))

        except Exception as e:
            error = str(e)

    return render_template("index.html", results=results, error=error, playlist_id=playlist_id,
                           playlist_url=playlist_url)


@app.route('/delete_playlist', methods=['POST'])
def delete_playlist():
    global PLAYLIST_ID, PLAYLIST_URL
    if PLAYLIST_ID:
        try:
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                                           client_secret=SPOTIPY_CLIENT_SECRET,
                                                           redirect_uri=SPOTIPY_REDIRECT_URI,
                                                           scope="playlist-modify-private"))
            sp.current_user_unfollow_playlist(PLAYLIST_ID)
        except Exception as e:
            print(f"Error deleting playlist: {e}")
        finally:
            PLAYLIST_ID = None
            PLAYLIST_URL = None
    return redirect(url_for('index'))


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get('PORT', 5001))
    app.run(host=host, port=port, debug=True)
