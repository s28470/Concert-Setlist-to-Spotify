from bs4 import BeautifulSoup
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

def extract_location_from_url(url):
    """
    Extracts the concert location from a setlist.fm URL.

    Args:
        url: The setlist.fm URL.

    Returns:
        The concert location (string) if found, None otherwise.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        setlist_headline = soup.find(class_="setlistHeadline")
        if setlist_headline:
            h1 = setlist_headline.find('h1')
            if h1:
                # Locate the span using its position relative to "at"
                location_parts = h1.find_all("span")
                for i, part in enumerate(location_parts):
                  if part.text.startswith("at"):
                    location_span = location_parts[i+1].find("span")
                    if location_span:
                      return location_span.text.strip()
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error during request to {url}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing {url}: {e}")
        return None


def get_band_name_and_songs(url):
    """
    Fetches a URL, parses the HTML, and extracts the band name and a list of song titles.

    Args:
        url: The URL to fetch and process.

    Returns:
        A dictionary with the following keys:
        - band_name: The band name (string) if found, None otherwise.
        - songs: A list of song titles (strings) if found, None otherwise.
        - error: An error message (string) if an error occurred, None otherwise.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        info_container = soup.find(class_='infoContainer')
        band_name = None
        songs = []

        if info_container:
            a_tag = info_container.find('a')
            if a_tag:
                span_tag = a_tag.find('span')
                if span_tag:
                    band_name = span_tag.text.strip()

        songs_list = soup.find(class_='songsList')
        if songs_list:
            li_elements = songs_list.find_all('li')
            for li in li_elements:
                a_tag_song_label = li.find('a', class_='songLabel')
                if a_tag_song_label:
                    song_title = a_tag_song_label.text.strip()
                    songs.append(song_title)

        location = extract_location_from_url(url)

        return {
            'band_name': band_name,
            'songs': songs or None,
            'error': None,
            'location': location
        }

    except requests.exceptions.RequestException as e:
        return {
            'band_name': None,
            'songs': None,
            'error': f"Error during request: {e}",
            'location': None
        }
    except Exception as e:
        return {
            'band_name': None,
            'songs': None,
            'error': f"An unexpected error occurred: {e}",
            'location': None
        }


def create_spotify_playlist(songs_lists, band_names, locations, sp):
    """
    Creates a single Spotify playlist with all given songs.

    Args:
        songs_lists: A list of lists of song titles (strings).
        band_names: A list of band names (strings).
        sp: The authenticated Spotify client.
        locations: A list of locations (strings).

    Returns:
        A dictionary containing the playlist's URL and ID.
    """
    all_songs = []
    all_bands = []
    all_locations=[]
    for index, songs in enumerate(songs_lists):
      if songs:
          all_songs.extend(songs)
          all_bands.extend([band_names[index]] * len(songs))
          all_locations.extend([locations[index]] * len(songs))
    if not all_songs:
        raise ValueError("There is no song to create the playlist")

    try:
        user_id = sp.me()["id"]
        playlist_name = "Multiple Setlists"
        if len(band_names) == 1:
             playlist_name = f"{band_names[0]} Setlist - {locations[0]}"
        playlist = sp.user_playlist_create(user_id, playlist_name, public=False)
        playlist_id = playlist["id"]

        song_uris = []
        for index, song in enumerate(all_songs):
          band_name = all_bands[index]
          result = sp.search(q=f"track:{song} artist:{band_name}", type="track", limit=5)
          found = False
          for track in result["tracks"]["items"]:
              track_artist = track["artists"][0]["name"].lower()
              if band_name.lower() in track_artist or track_artist in band_name.lower():
                  track_uri = track["uri"]
                  song_uris.append(track_uri)
                  found = True
                  break

          if not found:
                logging.warning(f"Could not find '{song}' by {band_name} on Spotify.")

        for i in range(0, len(song_uris), 100):
            sp.playlist_add_items(playlist_id, song_uris[i:i + 100])

        return {"url": playlist["external_urls"]["spotify"], "id": playlist_id}

    except spotipy.exceptions.SpotifyException as e:
        logging.error(f"An error occurred while interacting with the Spotify API: {e}")
        return {"error": f"An error occurred while interacting with the Spotify API: {e}"}
    except Exception as e:
        logging.error(f"An error occurred while interacting with the Spotify API: {e}")
        return {"error": f"An error occurred while interacting with the Spotify API: {e}"}
def rename_playlist(sp, playlist_id, playlist_name):
  try:
    sp.playlist_change_details(playlist_id, name=playlist_name)
  except Exception as e:
    logging.error(f"An error occurred while renaming the Spotify playlist: {e}")
    return {"error": f"An error occurred while renaming the Spotify playlist: {e}"}
