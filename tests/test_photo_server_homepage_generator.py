from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from photo_server_homepage_generator import (
    ASSET_SIZE_CLASSES,
    attach_adjacent_album_links,
    build_album_data,
    build_album_display_metadata,
    build_album_page_assets,
    find_matching_camera,
    find_matching_film_type,
    get_album_assets,
    get_all_shared_links,
    parse_album_metadata,
    parse_capture_date,
    render_album_pages,
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


def test_get_album_assets_searches_by_album_id():
    response = Mock()
    response.json.return_value = {
        "assets": {"items": [{"id": "asset-1"}], "nextPage": None}
    }

    with patch(
        "photo_server_homepage_generator.requests.post", return_value=response
    ) as post:
        assets = get_album_assets("https://immich.example/", "api-key", "album-1")

    post.assert_called_once_with(
        "https://immich.example/api/search/metadata",
        json={"albumIds": ["album-1"]},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": "api-key",
        },
        timeout=30,
    )
    response.raise_for_status.assert_called_once()
    assert assets == [{"id": "asset-1"}]


def test_get_album_assets_handles_missing_items():
    response = Mock()
    response.json.return_value = {"assets": {}}

    with patch(
        "photo_server_homepage_generator.requests.post", return_value=response
    ):
        assets = get_album_assets("https://immich.example", "api-key", "album-1")

    assert assets == []


def test_get_album_assets_follows_pagination_cursor():
    first_response = Mock()
    first_response.json.return_value = {
        "assets": {"items": [{"id": "asset-1"}], "nextPage": "2"}
    }
    second_response = Mock()
    second_response.json.return_value = {
        "assets": {"items": [{"id": "asset-2"}], "nextPage": None}
    }

    with patch(
        "photo_server_homepage_generator.requests.post",
        side_effect=[first_response, second_response],
    ) as post:
        assets = get_album_assets("https://immich.example", "api-key", "album-1")

    assert [call.kwargs["json"] for call in post.call_args_list] == [
        {"albumIds": ["album-1"]},
        {"albumIds": ["album-1"], "page": "2"},
    ]
    assert assets == [{"id": "asset-1"}, {"id": "asset-2"}]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Date Captured: 08/05/2025\nDate Scanned: 08/06/2025", "2025-08-05"),
        ("Date Captured: 8/5/2025 Date Scanned: 08/06/2025", "2025-08-05"),
    ],
)
def test_parse_capture_date(description, expected):
    assert parse_capture_date(description) == expected


def test_parse_album_metadata_extracts_every_field_in_order():
    description = (
        "Josh's 30th Birthday Roast, Boston\n\n"
        "Date Captured: 07/25/2026\n"
        "Date Scanned: 07/30/2026\n"
        "Public: True\n"
        "Film Stock: Kodak Ultramax 400\n"
        "Camera: Nikon Teletouch\n"
        "Lens: Nikon Macro\n"
        "F number: f/2.8\n"
        "Focal Length: 35mm\n"
        "Flash: Built-in\n"
    )

    assert parse_album_metadata(description) == [
        ("Date Captured", "07/25/2026"),
        ("Date Scanned", "07/30/2026"),
        ("Film Stock", "Kodak Ultramax 400"),
        ("Camera", "Nikon Teletouch"),
        ("Lens", "Nikon Macro"),
        ("F number", "f/2.8"),
        ("Focal Length", "35mm"),
        ("Flash", "Built-in"),
    ]


def test_parse_album_metadata_ignores_title_preamble_and_missing_date_captured():
    assert parse_album_metadata("Some Title: With A Colon\nPublic: True") == []


def test_build_album_display_metadata_attaches_urls_and_drops_date_captured():
    metadata_pairs = [
        ("Date Captured", "07/25/2026"),
        ("Film Stock", "Kodak Ultramax 400"),
        ("Camera", "Nikon Teletouch"),
        ("Lens", "Nikon Macro"),
    ]

    result = build_album_display_metadata(
        metadata_pairs,
        film_type_url="https://www.filmtypes.com/films/kodak-ultramax-400",
        camera_url="https://www.filmtypes.com/cameras/nikon-teletouch",
    )

    assert result == [
        {
            "label": "Film Stock",
            "value": "Kodak Ultramax 400",
            "url": "https://www.filmtypes.com/films/kodak-ultramax-400",
        },
        {
            "label": "Camera",
            "value": "Nikon Teletouch",
            "url": "https://www.filmtypes.com/cameras/nikon-teletouch",
        },
        {"label": "Lens", "value": "Nikon Macro", "url": None},
    ]


def test_build_album_data_includes_cover_thumbnail_if_available():
    with patch(
        "photo_server_homepage_generator.get_asset_thumbnail_data_url",
        return_value="data:image/png;base64,TEST",
    ), patch(
        "photo_server_homepage_generator.get_album_assets",
        return_value=[],
    ):
        with patch(
            "photo_server_homepage_generator.get_film_types_from_filmtypes_com",
            return_value={},
        ):
            with patch(
                "photo_server_homepage_generator.get_cameras_from_filmtypes_com",
                return_value={},
            ):
                shared_links = [
                    {
                        "key": "album-key",
                        "album": {
                            "id": "album-1",
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

    with patch(
        "photo_server_homepage_generator.get_film_types_from_filmtypes_com",
        return_value={},
    ):
        with patch(
            "photo_server_homepage_generator.get_cameras_from_filmtypes_com",
            return_value={},
        ):
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
        "page_url": "albums/newer.html",
        "assets": [],
        "metadata": [
            {"label": "Date Scanned", "value": "02/04/2025", "url": None},
            {"label": "Film Stock", "value": "HP5", "url": None},
            {"label": "Development Notes", "value": "Pushed one stop", "url": None},
            {"label": "Camera", "value": "Leica M6", "url": None},
            {"label": "Lens", "value": "35mm", "url": None},
        ],
        "newer_album": None,
        "older_album": {"name": "Older Album", "filename": "older.html"},
    }
    assert albums[1]["newer_album"] == {
        "name": "Newer Album",
        "filename": "newer.html",
    }
    assert albums[1]["older_album"] is None


def test_build_album_page_assets_builds_public_thumbnail_and_original_urls():
    raw_assets = [
        {"id": "asset-1", "originalFileName": "photo1.jpg"},
        {"id": "asset-2", "originalFileName": "photo2.jpg"},
    ]

    with patch(
        "photo_server_homepage_generator.random.choices",
        return_value=["size-md"],
    ):
        assets = build_album_page_assets(
            raw_assets, "https://immich.example/", "share-key"
        )

    assert assets == [
        {
            "filename": "photo1.jpg",
            "thumbnail_url": (
                "https://immich.example/api/assets/asset-1/thumbnail"
                "?key=share-key"
            ),
            "original_url": (
                "https://immich.example/api/assets/asset-1/original"
                "?key=share-key"
            ),
            "size_class": "size-md",
        },
        {
            "filename": "photo2.jpg",
            "thumbnail_url": (
                "https://immich.example/api/assets/asset-2/thumbnail"
                "?key=share-key"
            ),
            "original_url": (
                "https://immich.example/api/assets/asset-2/original"
                "?key=share-key"
            ),
            "size_class": "size-md",
        },
    ]


def test_build_album_page_assets_size_class_is_always_a_known_class():
    raw_assets = [
        {"id": f"asset-{i}", "originalFileName": f"p{i}.jpg"} for i in range(30)
    ]

    assets = build_album_page_assets(raw_assets, "https://immich.example", "key")

    assert all(asset["size_class"] in ASSET_SIZE_CLASSES for asset in assets)


def test_build_album_page_assets_handles_missing_inputs():
    assert build_album_page_assets([], None, "key") == []
    assert build_album_page_assets([], "https://immich.example", None) == []


def test_build_album_data_populates_assets_from_search_metadata():
    shared_links = [
        {
            "key": "album-key",
            "album": {
                "id": "album-1",
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
            },
        }
    ]

    with patch(
        "photo_server_homepage_generator.get_album_assets",
        return_value=[{"id": "asset-1", "originalFileName": "photo1.jpg"}],
    ) as get_assets, patch(
        "photo_server_homepage_generator.random.choices",
        return_value=["size-sm"],
    ), patch(
        "photo_server_homepage_generator.get_film_types_from_filmtypes_com",
        return_value={},
    ), patch(
        "photo_server_homepage_generator.get_cameras_from_filmtypes_com",
        return_value={},
    ):
        albums = build_album_data(
            shared_links,
            share_base_url="https://photos.example/share",
            immich_server_url="https://immich.example",
            immich_api_key="api-key",
        )

    get_assets.assert_called_once_with(
        "https://immich.example", "api-key", "album-1"
    )
    assert albums[0]["assets"] == [
        {
            "filename": "photo1.jpg",
            "thumbnail_url": (
                "https://immich.example/api/assets/asset-1/thumbnail"
                "?key=album-key"
            ),
            "original_url": (
                "https://immich.example/api/assets/asset-1/original"
                "?key=album-key"
            ),
            "size_class": "size-sm",
        }
    ]


def test_build_album_data_skips_asset_fetch_without_api_key():
    shared_links = [
        {
            "key": "album-key",
            "album": {
                "id": "album-1",
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
            },
        }
    ]

    with patch(
        "photo_server_homepage_generator.get_album_assets"
    ) as get_assets, patch(
        "photo_server_homepage_generator.get_film_types_from_filmtypes_com",
        return_value={},
    ), patch(
        "photo_server_homepage_generator.get_cameras_from_filmtypes_com",
        return_value={},
    ):
        albums = build_album_data(
            shared_links,
            share_base_url="https://photos.example/share",
            immich_server_url="https://immich.example",
            immich_api_key=None,
        )

    get_assets.assert_not_called()
    assert albums[0]["assets"] == []


def test_attach_adjacent_album_links_chains_newer_and_older():
    albums = [
        {"name": "Newest", "page_url": "albums/a.html"},
        {"name": "Middle", "page_url": "albums/b.html"},
        {"name": "Oldest", "page_url": "albums/c.html"},
    ]

    result = attach_adjacent_album_links(albums)

    assert result is albums
    assert albums[0]["newer_album"] is None
    assert albums[0]["older_album"] == {"name": "Middle", "filename": "b.html"}
    assert albums[1]["newer_album"] == {"name": "Newest", "filename": "a.html"}
    assert albums[1]["older_album"] == {"name": "Oldest", "filename": "c.html"}
    assert albums[2]["newer_album"] == {"name": "Middle", "filename": "b.html"}
    assert albums[2]["older_album"] is None


def test_attach_adjacent_album_links_handles_single_album():
    albums = [{"name": "Only", "page_url": "albums/only.html"}]

    attach_adjacent_album_links(albums)

    assert albums[0]["newer_album"] is None
    assert albums[0]["older_album"] is None


def test_build_album_data_skips_malformed_public_albums():
    with patch(
        "photo_server_homepage_generator.get_film_types_from_filmtypes_com",
        return_value={},
    ):
        with patch(
            "photo_server_homepage_generator.get_cameras_from_filmtypes_com",
            return_value={},
        ):
            albums = build_album_data(
                [
                    {
                        "key": "bad",
                        "album": {"albumName": "Bad", "description": "Public: True"},
                    }
                ]
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
                "page_url": "albums/album.html",
                "assets": [],
            }
        ],
        generated_at=datetime(2025, 8, 6, 7, 8, 9),
    )

    assert "Album" in html
    assert "albums/album.html" in html
    assert "2025-08-06 07:08:09" in html


def test_render_album_pages_includes_metadata_and_images():
    pages = render_album_pages(
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
                "page_url": "albums/album.html",
                "assets": [
                    {
                        "filename": "photo1.jpg",
                        "thumbnail_url": "https://immich.example/thumb/1",
                        "original_url": "https://immich.example/original/1",
                    }
                ],
            }
        ],
        generated_at=datetime(2025, 8, 6, 7, 8, 9),
    )

    assert list(pages.keys()) == ["albums/album.html"]
    html = pages["albums/album.html"]
    assert "Album" in html
    assert "Description" in html
    assert "https://immich.example/thumb/1" in html
    assert "https://immich.example/original/1" in html
    assert "../index.html" in html
    assert "2025-08-06 07:08:09" in html


def test_render_album_pages_includes_adjacent_album_nav_and_lightbox_data():
    pages = render_album_pages(
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
                "page_url": "albums/album.html",
                "assets": [
                    {
                        "filename": "photo1.jpg",
                        "thumbnail_url": "https://immich.example/thumb/1",
                        "original_url": "https://immich.example/original/1",
                        "size_class": "size-lg",
                    }
                ],
                "newer_album": {"name": "Newer One", "filename": "newer.html"},
                "older_album": {"name": "Older One", "filename": "older.html"},
            }
        ]
    )

    html = pages["albums/album.html"]
    # Album pages all live in the same directory, so the nav links must be
    # bare filenames (not "albums/<file>.html", which would double up the
    # subdirectory and 404 from within albums/album.html)
    assert 'href="newer.html"' in html
    assert "Newer One" in html
    assert 'href="older.html"' in html
    assert "Older One" in html
    assert "albums/newer.html" not in html
    assert "albums/older.html" not in html
    # Asset data is embedded for the JS lightbox to page through full-size images
    assert "https://immich.example/original/1" in html
    assert "id=\"lightbox\"" in html


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
