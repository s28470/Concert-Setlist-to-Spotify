from flask import Flask, render_template, request, redirect, url_for, session, flash
import os
import sys
import logging
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

# Configure logging to output to stdout
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(stream_handler)
logger.debug("Debug message")

# Add the directory containing main.py to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import get_band_name_and_songs, create_spotify_playlist, rename_playlist

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

# Spotify configuration
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
SCOPE = "playlist-modify-private"

def get_spotify_oauth():
    # Returns a SpotifyOAuth instance
    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE
    )

def get_spotify_client():
    # Returns an authenticated Spotify client or a redirect if no token is available
    sp_oauth = get_spotify_oauth()
    token_info = session.get("token_info", None)
    if not token_info:
        auth_url = sp_oauth.get_authorize_url()
        return redirect(auth_url)
    # Refresh token if expired
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
        session["token_info"] = token_info
    access_token = token_info["access_token"]
    return spotipy.Spotify(auth=access_token)

@app.route("/callback")
def callback():
    # Callback route to handle Spotify's redirect and token exchange
    sp_oauth = get_spotify_oauth()
    code = request.args.get("code")
    if not code:
        flash("Authorization failed", "error")
        return redirect(url_for("index"))
    token_info = sp_oauth.get_access_token(code)
    session["token_info"] = token_info
    return redirect(url_for("index"))

@app.route("/", methods=["GET", "POST"])
def index():
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
                        if isinstance(sp, spotipy.Spotify):
                            rename_playlist(sp, playlist_id, f"{band_name} Setlist - {location}")
                            flash("Playlist renamed successfully", "success")
                        else:
                            return sp  # redirect to authorization if needed
                    except Exception as e:
                        error = str(e)
                        logging.error(f"Error renaming playlist: {error}")
            return redirect(url_for('index'))

        urls = request.form.getlist("url")
        client_or_redirect = get_spotify_client()
        # If a redirect was returned, return it
        if not isinstance(client_or_redirect, spotipy.Spotify):
            return client_or_redirect
        sp = client_or_redirect

        songs_lists = []
        band_names = []
        locations = []
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

        try:
            playlist_data = create_spotify_playlist(songs_lists, band_names, locations, sp)
            if playlist_data.get("error"):
                error = playlist_data.get("error")
            else:
                session["playlist_id"] = playlist_data["id"]
                playlist_id = session["playlist_id"]
                # Get full playlist info
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
    # Delete (unfollow) the playlist and clear session data
    playlist_id = session.get("playlist_id")
    if playlist_id:
        try:
            client_or_redirect = get_spotify_client()
            if not isinstance(client_or_redirect, spotipy.Spotify):
                return client_or_redirect
            sp = client_or_redirect
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

if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get('PORT', 5001))
    app.run(host=host, port=port, debug=False)