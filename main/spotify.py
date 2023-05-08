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


def saved_tracks_to_playlist(data: dict = None) -> None:
    """ Adds all user liked songs to playlist of choice
    `dict`: Playlist object"""

    ids = get_saved_tracks()
    print(f"Found {len(ids)} songs in your liked tracks")
    if not data:
        data = spotify.playlist(input('\nEnter playlist ID or link: '))

    add_songs(data['id'], ids)


def remove_saved_tracks(ids=None) -> None:
    """ Removes all the user liked tracks
    `ids`: List of tracks to remove from the saved tracks:
    """

    ids = ids or get_saved_tracks()
    print(f"Found {len(ids)} tracks.")
    id_chunks = split_chunks(ids, 50)
    confirmation = input("Do you wish to delete (yes/no): ")

    for ids in id_chunks:
        spotify.current_user_saved_tracks_delete(
            tracks=ids) if 'y' in confirmation else print("Process terminated!")
    print("Removed all saved tracks.")


function = {1: mix_playlists, 2: shuffle_tracks,
            3: shuffle_all_my_playlists, 4: saved_tracks_to_playlist, 5: remove_saved_tracks}
option = 1
while option:
    """Simple input Menu"""

    option = input("""
    1. Mix playlists (Required playlists to get tracks, a playlist[own | collaberative] to add songs.)
    2. Shuffle tracks in playlist (Note: Removes and Re-adds songs doesn't reorder)
    3. Shuffle all your playlists at once
    4. Add all liked songs to playlist
    5. Remove tracks from liked sogns

    Select number only! Press Enter to quit.

    Enter option number: """)
    option = int(option) if option.isdigit() else None
    function[option]() if option else print("Closing!")
