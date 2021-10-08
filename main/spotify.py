from utils import *


def mix_playlists() -> None:
    """Gets mulitple playlists and adds into one"""

    play_id = "_"
    _ids = []

    # Getting multple playlists to add songs in a playlist
    while play_id:
        play_id = input("Enter playlist ID or link: ")
        if play_id:
            _ids.extend(get_tracks(play_id, "playlist"))

    ids = list(set(_ids))
    print(f"\nTotal songs: {len(ids)}")
    print(f"Duplicates: {len(_ids) - len(ids)}\n")

    # playlist to add songs
    playlist = spotify.playlist(input("\nEnter your playlist ID or link: "))

    shuffle(ids)
    remove_songs(playlist["id"], ids)
    add_songs(playlist["id"], ids)


def shuffle_tracks(data: dict = None) -> None:
    """Removes all tracks from playlist and adds it back in a different order
    `dict`: Playlist object"""

    if not data:
        data = spotify.playlist(input('\nEnter playlist ID or link: '))

    ids = get_tracks(data["external_urls"]["spotify"])
    print("\nExtracted", len(ids), "songs from", data["name"])

    # Removes the songs form playlist
    remove_songs(data["id"], ids)

    # Shuffling the tracks
    shuffle(ids)

    # Adds the songs in different order
    add_songs(data["id"], ids)


def shuffle_all_my_playlists(ignored=None) -> None:
    """Shuffles all user owned playlist except ignored playlists provied by user
    `ignored`: Accepted formats: playlist links, ids, partial/full names (case insensitive), """

    ignored = ignored or input(
        "Enter playlists to ignore (Seprated by ',')\nPress Enter if None: ").split(",")
    ignored_ids = []
    for i in ignored:
        link = SPOTIFY_REG.match(i)
        ignored_ids.append(link[3] if link and link[2] == "playlist" else i)

    for playlist in get_owned_playlists():
        if playlist["id"] in ignored_ids or any([i.lower() in playlist["name"].lower() for i in ignored_ids]):
            print(f"\nIgnored: {playlist['name']}")
            continue

        shuffle_tracks(playlist)


function = {1: mix_playlists, 2: shuffle_tracks, 3: shuffle_all_my_playlists}
option = 1
while option:
    """Simple input Menu"""

    option = input("""
    1. Mix playlists(Required playlists to get tracks, a playlist(own/collaberative) to add songs.)
    2. Shuffle tracks in playlist(Note: Removes and Re-adds songs doesn't reorder
    3. Shuffle all your playlists at once
    Select number only! Press Enter to quit.

    Enter option number: """)
    option = int(option) if option.isdigit() else None
    function[option]() if option else print("Closing!")
