import pytest

from spotify_mcp.utils.links import parse_ref, to_uri

PL = "37i9dQZF1DXcBWIGoYBM5M"
TR = "4uLU6hMCjMI75M1A2tKUQC"


@pytest.mark.parametrize(
    ("ref", "expect", "result"),
    [
        (f"https://open.spotify.com/playlist/{PL}?si=abc&pi=x", None, ("playlist", PL)),
        (f"http://open.spotify.com/track/{TR}", None, ("track", TR)),
        (f"https://open.spotify.com/track/{TR}/", None, ("track", TR)),
        (f"https://open.spotify.com/intl-pt/track/{TR}", None, ("track", TR)),
        (f"spotify:playlist:{PL}", None, ("playlist", PL)),
        (f"spotify:track:{TR}", None, ("track", TR)),
        (f"spotify:album:{TR}", None, ("album", TR)),
        (TR, "track", ("track", TR)),
        (f"  spotify:track:{TR}  ", None, ("track", TR)),
        (f"https://open.spotify.com/playlist/{PL}", "playlist", ("playlist", PL)),
    ],
)
def test_parse_ref_valid(ref, expect, result):
    assert parse_ref(ref, expect) == result


@pytest.mark.parametrize(
    ("ref", "expect"),
    [
        (TR, None),  # bare ID without a type
        ("", None),
        ("garbage", None),
        ("https://example.com/playlist/x", None),
        (f"https://open.spotify.com/show/{PL}", None),  # unsupported type
        (f"spotify:playlist:{PL}:extra", None),
        ("spotify:playlist:short", None),  # invalid ID length
        (f"https://open.spotify.com/track/{TR}", "playlist"),  # type mismatch
        ("chill vibes", "playlist"),  # name, not an ID
    ],
)
def test_parse_ref_invalid(ref, expect):
    with pytest.raises(ValueError):
        parse_ref(ref, expect)


def test_to_uri():
    assert to_uri("track", TR) == f"spotify:track:{TR}"
