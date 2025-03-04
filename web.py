from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import sys
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

# Add the directory containing main.py to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import get_band_name_and_songs, create_spotify_playlist, rename_playlist

app = Flask(__name__)
# Secret key for sessions; set it via the FLASK_SECRET_KEY environment variable
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

logging.basicConfig(filename='app.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Spotify configuration
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

def get_spotify_client():
    """Returns an authenticated Spotify client."""
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="playlist-modify-private"
    ))

@app.route("/", methods=["GET", "POST"])
def index():
    """
    Handles requests to the main page.
    On a POST request:
      - Renames the playlist if the rename option is chosen.
      - Processes setlist.fm URLs, extracts data, creates a playlist, and saves the data in the session.
    """
    results: List[Dict] = []
    error = None
    playlist_id = session.get("playlist_id")
    playlist_url = session.get("playlist_url")
    band_names_with_locations = session.get("band_names_with_locations", [])

    if request.method == "POST":
        if "rename" in request.form:
            if playlist_id:
                band_name_with_location = request.form.get("band_name_with_location")
                if band_name_with_location:
                    if " - " in band_name_with_location:
                        band_name, location = band_name_with_location.split(" - ", 1)
                    else:
                        band_name, location = band_name_with_location, ""
                    try:
                        sp = get_spotify_client()
                        rename_playlist(sp, playlist_id, f"{band_name} Setlist - {location}")
                        flash("Playlist renamed successfully", "success")
                    except Exception as e:
                        error = str(e)
                        logging.error(f"Error renaming playlist: {error}")
            return redirect(url_for('index'))

        urls = request.form.getlist("url")  # Get the list of URLs
        try:
            sp = get_spotify_client()
        except Exception as e:
            error = str(e)
            logging.error(f"Spotify client error: {error}")
            return render_template("index.html", results=results, error=error,
                                   playlist_id=playlist_id, playlist_url=playlist_url,
                                   band_names_with_locations=band_names_with_locations)

        songs_lists = []
        band_names = []
        locations = []
        temp_results = []
        band_names_with_locations = []

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
                    locations.append(location)
                    result["band_name"] = band_name
                    result["location"] = location
            except Exception as e:
                result["error"] = str(e)
                logging.error(f"Error processing URL {url}: {result['error']}")
            results.append(result)
            temp_results.append(result)

        try:
            playlist_data = create_spotify_playlist(songs_lists, band_names, locations, sp)
            if playlist_data.get("error"):
                error = playlist_data.get("error")
            else:
                session["playlist_id"] = playlist_data["id"]
                playlist_id = session["playlist_id"]
                # Get playlist details to retrieve the proper URL
                playlist_full_info = sp.playlist(playlist_id)
                session["playlist_url"] = playlist_full_info["external_urls"]["spotify"].replace(
                    "https://open.spotify.com/playlist/",
                    "https://open.spotify.com/embed/playlist/"
                )
                playlist_url = session["playlist_url"]

            if len(band_names) > 1:
                band_names_with_locations.append(", ".join(band_names) + " Playlist")
            for index, band_name in enumerate(band_names):
                band_names_with_locations.append(f"{band_name} - {locations[index]}")
            session["band_names_with_locations"] = band_names_with_locations

            return redirect(url_for('index'))

        except Exception as e:
            error = str(e)
            logging.error(f"Error creating playlist: {error}")

    return render_template("index.html", results=results, error=error,
                           playlist_id=playlist_id, playlist_url=playlist_url,
                           band_names_with_locations=band_names_with_locations)

@app.route('/delete_playlist', methods=['POST'])
def delete_playlist():
    """
    Deletes the user's playlist (unfollows it) and clears session data.
    """
    playlist_id = session.get("playlist_id")
    if playlist_id:
        try:
            sp = get_spotify_client()
            sp.current_user_unfollow_playlist(playlist_id)
            flash("Playlist deleted successfully", "success")
        except Exception as e:
            logging.error(f"Error deleting playlist: {e}")
            flash("Error deleting playlist", "error")
        finally:
            session.pop("playlist_id", None)
            session.pop("playlist_url", None)
            session.pop("band_names_with_locations", None)
    return redirect(url_for('index'))

from flask import send_from_directory

@app.route('/css/<path:filename>')
def send_css(filename):
    return send_from_directory('templates', filename)

@app.route('/js/<path:filename>')
def send_js(filename):
    return send_from_directory('templates', filename)

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get('PORT', 5001))
    # Debug mode is disabled for production
    app.run(host=host, port=port, debug=False)