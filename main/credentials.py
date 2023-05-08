import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

# Scope for required features
scope = "ugc-image-upload user-read-recently-played user-top-read user-read-playback-position user-read-playback-state user-modify-playback-state user-read-currently-playing app-remote-control streaming playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-follow-modify user-follow-read user-library-modify user-library-read user-read-email user-read-private"

client_data = {"client_id": "YOUR_CLIENT_ID", # Enter your client ID from the app page on developer portal
               "client_secret": "YOUR_CLIENT_SECRET"} # Enter your client secret from the app page on developer portal

# Spotify's login details
creds = SpotifyClientCredentials(**client_data)
auth = SpotifyOAuth(**client_data, **{"scope": scope,
                    "redirect_uri": "http://localhost:8080"})

spotify = spotipy.Spotify(auth_manager=auth)
