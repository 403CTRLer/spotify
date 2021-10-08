import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

# Scope for required features
scope = "ugc-image-upload user-read-recently-played user-top-read user-read-playback-position user-read-playback-state user-modify-playback-state user-read-currently-playing app-remote-control streaming playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-follow-modify user-follow-read user-library-modify user-library-read user-read-email user-read-private"

client_data = {"client_id": "5c721a3a40a34fd1b4e0d45e581e6af2",
               "client_secret": "43bd4a53899a4f63b20d9ee616776c4f"}

# Spotify's login details
creds = SpotifyClientCredentials(**client_data)
auth = SpotifyOAuth(**client_data, **{"scope": scope,
                    "redirect_uri": "http://localhost:8080"})

spotify = spotipy.Spotify(auth_manager=auth)
