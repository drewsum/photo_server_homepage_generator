from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from photo_server_homepage_generator import (
    build_album_data,
    find_matching_camera,
    find_matching_film_type,
    get_all_shared_links,
    parse_capture_date,
    render_homepage,
)


def test_get_all_shared_links_calls_immich_api():
    response = Mock()
    response.json.return_value = [{"id": "link-id"}]

    with patch(
        "photo_server_homepage_generator.requests.get", return_value=response
    ) as get:
        shared_links = get_all_shared_links("api-key", "https://immich.example/")

    get.assert_called_once_with(
        "https://immich.example/api/shared-links",
        headers={"Accept": "application/json", "x-api-key": "api-key"},
        timeout=30,
    )
    response.raise_for_status.assert_called_once()
    assert shared_links == [{"id": "link-id"}]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Date Captured: 08/05/2025\nDate Scanned: 08/06/2025", "2025-08-05"),
        ("Date Captured: 8/5/2025 Date Scanned: 08/06/2025", "2025-08-05"),
    ],
)
def test_parse_capture_date(description, expected):
    assert parse_capture_date(description) == expected


def test_build_album_data_includes_cover_thumbnail_if_available():
    with patch(
        "photo_server_homepage_generator.get_asset_thumbnail_data_url",
        return_value="data:image/png;base64,TEST",
    ):
        with patch("photo_server_homepage_generator.get_film_types_from_filmtypes_com", return_value={}):
            with patch("photo_server_homepage_generator.get_cameras_from_filmtypes_com", return_value={}):
                shared_links = [
                    {
                        "key": "album-key",
                        "album": {
                            "albumName": "Test Album (Shared)",
                            "description": (
                                "Test description\n"
                                "Date Captured: 01/01/2025\n"
                                "Date Scanned: 01/02/2025\n"
                                "Film Stock: Portra 400\n"
                                "Camera: Nikon F3\n"
                                "Lens: 50mm\n"
                                "Public: True"
                            ),
                            "albumThumbnailAssetId": "asset-id",
                        },
                    }
                ]

                albums = build_album_data(
                    shared_links,
                    share_base_url="https://photos.example/share",
                    immich_server_url="https://immich.example",
                    immich_api_key="api-key",
                )

    assert albums[0]["cover_thumbnail"] == "data:image/png;base64,TEST"


def test_build_album_data_returns_public_albums_sorted_by_date():
    shared_links = [
        {
            "key": "older",
            "album": {
                "albumName": "Older Album (Shared)",
                "description": (
                    "Older description\n"
                    "Date Captured: 01/02/2024\n"
                    "Date Scanned: 01/03/2024\n"
                    "Film Stock: Portra 400\n"
                    "Camera: Nikon F3\n"
                    "Lens: 50mm\n"
                    "Public: True"
                ),
            },
        },
        {
            "key": "private",
            "album": {
                "albumName": "Private Album",
                "description": "Public: False",
            },
        },
        {
            "key": "newer",
            "album": {
                "albumName": "Newer Album (Shared)",
                "description": (
                    "Newer description\n"
                    "Date Captured: 02/03/2025\n"
                    "Date Scanned: 02/04/2025\n"
                    "Film Stock: HP5\n"
                    "Development Notes: Pushed one stop\n"
                    "Camera: Leica M6\n"
                    "Lens: 35mm\n"
                    "Public: True"
                ),
            },
        },
    ]

    with patch("photo_server_homepage_generator.get_film_types_from_filmtypes_com", return_value={}):
        with patch("photo_server_homepage_generator.get_cameras_from_filmtypes_com", return_value={}):
            albums = build_album_data(
                shared_links, share_base_url="https://photos.example/share"
            )

    assert [album["name"] for album in albums] == ["Newer Album", "Older Album"]
    assert albums[0] == {
        "name": "Newer Album",
        "description": "Newer description\n",
        "date": "2025-02-03",
        "film_stock": "HP5",
        "film_type_url": None,
        "camera": "Leica M6",
        "camera_url": None,
        "cover_thumbnail": None,
        "link": "https://photos.example/share/newer",
    }


def test_build_album_data_skips_malformed_public_albums():
    with patch("photo_server_homepage_generator.get_film_types_from_filmtypes_com", return_value={}):
        with patch("photo_server_homepage_generator.get_cameras_from_filmtypes_com", return_value={}):
            albums = build_album_data(
                [{"key": "bad", "album": {"albumName": "Bad", "description": "Public: True"}}]
            )

    assert albums == []


def test_render_homepage_includes_album_and_generation_date():
    html = render_homepage(
        [
            {
                "name": "Album",
                "description": "Description",
                "date": "2025-08-05",
                "film_stock": "Portra",
                "film_type_url": None,
                "camera": "Nikon",
                "camera_url": None,
                "cover_thumbnail": None,
                "link": "https://photos.example/share/album",
            }
        ],
        generated_at=datetime(2025, 8, 6, 7, 8, 9),
    )

    assert "Album" in html
    assert "https://photos.example/share/album" in html
    assert "2025-08-06 07:08:09" in html


def test_find_matching_film_type_returns_matching_url():
    film_types = {
        "Kodak Portra 400": "https://www.filmtypes.com/films/kodak-portra-400",
        "Fujifilm Pro 400H": "https://www.filmtypes.com/films/fujifilm-pro-400h",
    }
    
    result = find_matching_film_type("Portra 400", film_types)
    assert result == "https://www.filmtypes.com/films/kodak-portra-400"


def test_find_matching_film_type_returns_none_for_no_match():
    film_types = {
        "Kodak Portra 400": "https://www.filmtypes.com/films/kodak-portra-400",
    }
    
    result = find_matching_film_type("Unknown Film", film_types)
    assert result is None


def test_find_matching_film_type_handles_empty_dict():
    result = find_matching_film_type("Portra 400", {})
    assert result is None


def test_find_matching_camera_returns_matching_url():
    cameras = {
        "Nikon F3": "https://www.filmtypes.com/cameras/nikon-f3",
        "Leica M6": "https://www.filmtypes.com/cameras/leica-m6",
    }
    
    result = find_matching_camera("Nikon F3", cameras)
    assert result == "https://www.filmtypes.com/cameras/nikon-f3"


def test_find_matching_camera_returns_none_for_no_match():
    cameras = {
        "Nikon F3": "https://www.filmtypes.com/cameras/nikon-f3",
    }
    
    result = find_matching_camera("Unknown Camera", cameras)
    assert result is None


def test_find_matching_camera_handles_empty_dict():
    result = find_matching_camera("Nikon F3", {})
    assert result is None
