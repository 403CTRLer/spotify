import traceback
import sys
from re import compile
from pprint import pprint
from random import shuffle
from credentials import spotify

# Spotify URI/URL regex
SPOTIFY_REG = compile(
    "^(https?://open.spotify.com/(playlist|track|album)/|spotify:(playlist|track|album):)([a-zA-Z0-9]+)(.*)$"
)


def playlist_iseditable(playlist, user=None) -> bool:
    """Check editability of a playlist
    Returns True if `user` is the owner of `playlist` or it is collaborative"""

    user_id = user or spotify.me()["id"]
    return playlist["collaborative"] or playlist["owner"]["id"] == user_id


def split_chunks(lst: list, size: int = 100) -> "list[list]":
    """Splits ids into list of list according to api limit
    `lst`: The list of ids
    `size`: Max length of inner list"""

    return [lst[i: i + size] for i in range(0, len(lst), size)]


def get_user_playlists(user: str = None, limit: int = None) -> list:
    """Gets user's playlists both owned and saved to library"""

    limit = limit or 50
    user_id = user or spotify.me()["id"]
    total = spotify.user_playlists(user_id)["total"]

    return [
        j
        for i in range(0, total, limit)
        for j in spotify.user_playlists(user_id, limit=limit, offset=i)["items"]
    ]


def get_owned_playlists(user: str = None) -> list:
    """Returns user owned playlists"""

    user_id = user or spotify.me()["id"]
    playlists = get_user_playlists(user_id)

    return [playlist for playlist in playlists if playlist["owner"]["id"] == user_id]


def get_tracks(link: str, type: str = None) -> list:
    """Gets a valid spotify link or id & type and returns list of ids of tracks from link
    `link`: spotify link or ID
    `type`: (playlist | album | track) required if ID is passed"""

    spotify_link = SPOTIFY_REG.match(link)

    if spotify_link:
        type = spotify_link.groups()[1]
        spotify_id = spotify_link.groups()[3]

    elif type:
        spotify_id = link

    else:
        raise TypeError

    if type == "track":
        return [spotify_id]

    elif type == "playlist":
        data, limit = spotify.playlist(
            spotify_id, fields="tracks.total, id"), 100
        return [
            j["track"]["id"]
            for i in range(0, data["tracks"]["total"], limit)
            for j in spotify.playlist_tracks(data["id"], limit=limit, offset=i)["items"]
        ]

    elif type == "album":
        data, limit = spotify.album(spotify_id), 50
        return [
            j["id"]
            for i in range(0, data["tracks"]["total"], limit)
            for j in spotify.album_tracks(data["id"], limit=limit, offset=i)["items"]
        ]


def remove_songs(playlist_id: str, ids: list, size: int = 100) -> None:
    print("Removing songs...", end=" -> ")

    id_chunks = split_chunks(ids, size)
    try:

        for ids in id_chunks:
            spotify.playlist_remove_all_occurrences_of_items(playlist_id, ids)
    except Exception as error:
        print("Unsucessfull")
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )
    else:
        print("Successfull")


def add_songs(playlist_id: str, ids: list, size: int = 100) -> None:
    print("Adding songs ...", end=" -> ")

    id_chunks = split_chunks(ids, size)
    try:
        for ids in id_chunks:
            spotify.playlist_add_items(playlist_id, ids)
    except Exception as error:
        with open("temp", "w") as f:
            f.write(str(ids))

        print("Unsucessfull")
        traceback.print_exception(
            type(error), error, error.__traceback__, file=sys.stderr
        )
    else:
        print("Successfull")
