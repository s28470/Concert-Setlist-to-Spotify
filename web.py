from flask import Flask, render_template, request
import os
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

# Add the directory containing main.py to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import get_band_name_and_songs, create_spotify_playlist, extract_location_from_url

app = Flask(__name__)

# Configure your Spotify app credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

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
    playlist_url = None
    playlist_id = None  # Initialize playlist_id
    error = None
    band_name = None
    songs = None
    location = None

    if request.method == "POST":
        url = request.form["url"]
        result = get_band_name_and_songs(url)

        if result["error"]:
            error = result["error"]
        elif not result["band_name"] or not result["songs"]:
            error = "Could not extract band name or songs from the URL."
        else:
            band_name = result["band_name"]
            songs = result["songs"]
            location = extract_location_from_url(url)

            # Spotify Auth
            try:
                sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                                                                client_secret=SPOTIPY_CLIENT_SECRET,
                                                                redirect_uri=SPOTIPY_REDIRECT_URI,
                                                                scope="playlist-modify-private"))

                playlist_data = create_spotify_playlist(band_name, songs, sp, location)
                playlist_url = playlist_data["url"]
                playlist_id = playlist_data["id"]
            except Exception as e:
                error = str(e)

    return render_template("index.html", playlist_url=playlist_url, playlist_id=playlist_id, error=error, band_name=band_name, location=location)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port, debug=False)  # Set debug to False or remove it entirely
