"""
Photo Server Homepage Generator

This script generates an HTML homepage for public photo albums from an Immich server.
It scrapes film and camera information from filmtypes.com to create hyperlinks for
film stocks and cameras, providing users with detailed information about their gear.

Features:
- Fetches public albums from Immich server
- Downloads album cover thumbnails
- Matches film stocks and cameras to filmtypes.com database
- Generates responsive HTML homepage with search and filtering
- Rich terminal output with progress bars and status indicators

Dependencies:
- requests: HTTP requests to Immich API and filmtypes.com
- beautifulsoup4: HTML parsing for filmtypes.com scraping
- rapidfuzz: Fuzzy string matching for film/camera name matching
- jinja2: HTML template rendering
- rich: Beautiful terminal output and progress bars
- python-dotenv: Environment variable loading
"""

import base64
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from rapidfuzz import fuzz
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table

# Global console instance for rich terminal output
console = Console()

# Default paths and URLs - can be overridden by environment variables
DEFAULT_OUTPUT_PATH = "/output/index.html"
DEFAULT_SHARE_BASE_URL = "https://photos.drewsum.us/share"

# Caching dictionaries to avoid repeated API calls and web scraping
_thumbnail_cache = {}  # Cache for album cover thumbnails
# (server_url + asset_id -> base64 data URL)
_film_types_cache = None  # Cache for film types from filmtypes.com
# (film_name -> URL)
_cameras_cache = None  # Cache for cameras from filmtypes.com
# (camera_name -> URL)


def get_film_types_from_filmtypes_com():
    """
    Scrape all film types from filmtypes.com and return a dict of name -> url.

    This function fetches the complete list of analog film stocks from filmtypes.com
    and creates a mapping from film names to their detail page URLs. The data is
    cached globally to avoid repeated web requests during a single execution.

    Returns:
        dict: Mapping of film type names to their filmtypes.com URLs
              Example: {"Kodak Portra 400": "https://www.filmtypes.com/films/kodak-portra-400"}
    """
    global _film_types_cache

    # Return cached data if already fetched
    if _film_types_cache is not None:
        return _film_types_cache

    try:
        # Show progress spinner while fetching data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching film types from filmtypes.com...", total=None)
            # Fetch the main films page from filmtypes.com
            response = requests.get("https://www.filmtypes.com/films", timeout=30)
            response.raise_for_status()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, "html.parser")

        # Initialize dictionary to store film type mappings
        film_types = {}

        # Find all anchor tags with href attributes
        # Film types appear as links in the format /films/film-name
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Check if this is a film detail page link
            if href.startswith("/films/") and href != "/films":
                # Extract the film name from the link text
                film_name = link.get_text(strip=True)

                # Filter out non-film links (like "All Film Stocks")
                if film_name and film_name.lower() != "all film stocks":
                    # Create full URL and store in dictionary
                    film_types[film_name] = f"https://www.filmtypes.com{href}"

        # Cache the results for future use
        _film_types_cache = film_types
        console.print(f"[green]✓[/green] Loaded [bold]{len(film_types)}[/bold] "
                      "film types")
        return film_types

    except Exception as error:
        console.print(f"[red]✗[/red] Could not fetch film types: {error}")
        return {}


def find_matching_film_type(film_stock, film_types_dict):
    """
    Use fuzzy matching to find the best matching film type URL.

    This function performs fuzzy string matching between a film stock name
    from album metadata and the available film types from filmtypes.com.
    It uses token_set_ratio for better matching of film names that may have
    slight variations in formatting or naming conventions.

    Args:
        film_stock (str): Film stock name from album description (e.g., "Portra 400")
        film_types_dict (dict): Dictionary of film names to URLs from filmtypes.com

    Returns:
        str or None: URL of the best matching film type, or None if no good match found
    """
    # Return None if no film stock provided or no film types to match against
    if not film_stock or not film_types_dict:
        return None

    # Initialize variables to track the best match
    best_match = None
    best_score = 0
    # Minimum similarity threshold (85% - allows for minor variations)
    threshold = 85

    # Iterate through all available film types
    for film_name, film_url in film_types_dict.items():
        # Use token_set_ratio for robust matching that handles:
        # - Different word orders (e.g., "Kodak Portra 400" vs "Portra 400 Kodak")
        # - Partial matches and abbreviations
        # - Case insensitive matching
        score = fuzz.token_set_ratio(film_stock.lower(), film_name.lower())

        # Update best match if this score is higher and above threshold
        if score > best_score and score >= threshold:
            best_score = score
            best_match = film_url

    return best_match


def get_cameras_from_filmtypes_com():
    """
    Scrape all cameras from filmtypes.com and return a dict of name -> url.

    Similar to get_film_types_from_filmtypes_com(), this function fetches the
    complete list of analog cameras from filmtypes.com and creates a mapping
    from camera names to their detail page URLs. Results are cached globally.

    Returns:
        dict: Mapping of camera names to their filmtypes.com URLs
              Example: {"Nikon F3": "https://www.filmtypes.com/cameras/nikon-f3"}
    """
    global _cameras_cache

    # Return cached data if already fetched
    if _cameras_cache is not None:
        return _cameras_cache

    try:
        # Show progress spinner while fetching data
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching cameras from filmtypes.com...", total=None)
            # Fetch the cameras page from filmtypes.com
            response = requests.get("https://www.filmtypes.com/cameras", timeout=30)
            response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.content, "html.parser")

        # Initialize dictionary for camera mappings
        cameras = {}

        # Find all camera detail page links
        # Camera links follow the pattern /cameras/camera-name
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Check if this is a camera detail page link
            if href.startswith("/cameras/") and href != "/cameras":
                # Extract camera name from link text
                camera_name = link.get_text(strip=True)

                # Filter out non-camera links (like "All Film Cameras")
                if camera_name and camera_name.lower() != "all film cameras":
                    # Create full URL and store in dictionary
                    cameras[camera_name] = f"https://www.filmtypes.com{href}"

        # Cache the results
        _cameras_cache = cameras
        console.print(f"[green]✓[/green] Loaded [bold]{len(cameras)}[/bold] cameras")
        return cameras

    except Exception as error:
        console.print(f"[red]✗[/red] Could not fetch cameras: {error}")
        return {}


def find_matching_camera(camera_name, cameras_dict):
    """
    Use fuzzy matching to find the best matching camera URL.

    Similar to find_matching_film_type(), this function performs fuzzy string
    matching between a camera name from album metadata and the available cameras
    from filmtypes.com. Uses the same token_set_ratio algorithm for robust matching.

    Args:
        camera_name (str): Camera name from album description (e.g., "Nikon F3")
        cameras_dict (dict): Dictionary of camera names to URLs from filmtypes.com

    Returns:
        str or None: URL of the best matching camera, or None if no good match found
    """
    # Return None if no camera name provided or no cameras to match against
    if not camera_name or not cameras_dict:
        return None

    # Initialize variables to track the best match
    best_match = None
    best_score = 0
    # Same threshold as film matching for consistency
    threshold = 85

    # Iterate through all available cameras
    for cam_name, cam_url in cameras_dict.items():
        # Use token_set_ratio for robust matching that handles:
        # - Different naming conventions (e.g., "Nikon F3" vs "F3 Nikon")
        # - Abbreviations and partial matches
        # - Case insensitive matching
        score = fuzz.token_set_ratio(camera_name.lower(), cam_name.lower())

        # Update best match if this score is higher and above threshold
        if score > best_score and score >= threshold:
            best_score = score
            best_match = cam_url

    return best_match


def get_all_shared_links(api_key, url):
    """
    Fetch all shared links from the Immich server.

    Makes an authenticated API call to the Immich server's shared-links endpoint
    to retrieve information about all publicly shared albums.

    Args:
        api_key (str): Immich API key for authentication
        url (str): Base URL of the Immich server

    Returns:
        list: List of shared link objects from Immich API

    Raises:
        requests.HTTPError: If the API request fails
    """
    # Set up authentication headers
    headers = {"Accept": "application/json", "x-api-key": api_key}

    # Make GET request to shared-links endpoint
    response = requests.get(
        f"{url.rstrip('/')}/api/shared-links",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def load_config():
    """
    Load configuration from environment variables.

    Reads the Immich server URL and API key from environment variables
    (typically loaded from a .env file). Provides user feedback about
    configuration status.

    Returns:
        tuple: (immich_server_url, immich_api_key) - may be None if not set
    """
    # Load environment variables from .env file if present
    load_dotenv()

    # Read configuration values
    immich_server_url = os.getenv("IMMICH_SERVER")
    immich_api_key = os.getenv("IMMICH_API_KEY")

    # Provide user feedback about configuration status
    if immich_server_url is not None:
        console.print(f"[green]✓[/green] Server URL: {immich_server_url}")
    else:
        console.print("[red]✗[/red] IMMICH_SERVER environment variable not found")

    if immich_api_key is not None:
        console.print("[green]✓[/green] Immich API key loaded")
    else:
        console.print("[red]✗[/red] IMMICH_API_KEY environment variable not found")

    return immich_server_url, immich_api_key


def parse_capture_date(description):
    """
    Parse the capture date from album description.

    Extracts and parses the capture date from the structured album description
    format. The date appears in MMDDYYYY format and is converted to YYYY-MM-DD.

    Args:
        description (str): Album description containing date information

    Returns:
        str: Formatted date string in YYYY-MM-DD format

    Raises:
        ValueError: If date parsing fails
    """
    # Extract date string from description format:
    # "Date Captured: [date] Date Scanned: [date]"
    date_text = (
        description.split("Date Captured:")[1]
        .split("Date Scanned:")[0]
        .strip("\n")
        .strip(" ")
        .replace("/", "")  # Remove any slashes
    )
    # Parse MMDDYYYY format and convert to YYYY-MM-DD
    return datetime.strptime(date_text, "%m%d%Y").strftime("%Y-%m-%d")


def get_asset_thumbnail_data_url(server_url, api_key, asset_id):
    """
    Fetch an asset thumbnail and return it as a base64 data URL.

    Downloads a thumbnail image for an Immich asset and converts it to a
    base64 data URL that can be embedded directly in HTML. Results are
    cached to avoid redundant downloads.

    Args:
        server_url (str): Immich server base URL
        api_key (str): Immich API key for authentication
        asset_id (str): Asset ID for the thumbnail to fetch

    Returns:
        str or None: Base64 data URL (data:image/webp;base64,...), or None if failed
    """
    # Validate required parameters
    if not server_url or not api_key or not asset_id:
        return None

    # Check cache first to avoid redundant downloads
    cache_key = (server_url.rstrip("/"), asset_id)
    if cache_key in _thumbnail_cache:
        return _thumbnail_cache[cache_key]

    # Construct thumbnail API endpoint URL
    thumbnail_url = f"{server_url.rstrip('/')}/api/assets/{asset_id}/thumbnail"
    headers = {"Accept": "*/*", "x-api-key": api_key}

    try:
        # Fetch the thumbnail image
        response = requests.get(thumbnail_url, headers=headers, timeout=30)
        response.raise_for_status()

        # Convert image to base64 data URL
        content_type = response.headers.get("content-type", "image/webp")
        encoded = base64.b64encode(response.content).decode("ascii")
        data_url = f"data:{content_type};base64,{encoded}"

        # Cache the result
        _thumbnail_cache[cache_key] = data_url
        return data_url
    except Exception as error:
        console.print(f"[yellow]⚠[/yellow] Could not fetch thumbnail for "
                      f"asset {asset_id}: {error}")
        return None


def build_album_data(
    shared_links,
    share_base_url=DEFAULT_SHARE_BASE_URL,
    immich_server_url=None,
    immich_api_key=None,
):
    """
    Process shared links into enriched album data with thumbnails and
    film/camera matching.

    This is the core data processing function that transforms raw Immich
    shared
    link data into enriched album objects with thumbnails, film type hyperlinks,
    and camera hyperlinks. The function processes albums in three phases:
    1. Fetch album cover thumbnails
    2. Match film stocks and cameras to filmtypes.com
    3. Build final album data structures

    Args:
        shared_links (list): List of shared link objects from Immich API
        share_base_url (str): Base URL for generating album share links
        immich_server_url (str): Immich server URL for thumbnail fetching
        immich_api_key (str): Immich API key for thumbnail fetching

    Returns:
        list: List of album dictionaries sorted by date (newest first), each containing:
              - name: Album name
              - cover_thumbnail: Base64 data URL of album cover
              - description: Album description
              - date: Capture date in YYYY-MM-DD format
              - film_stock: Extracted film stock name
              - film_type_url: URL to film type page (if matched)
              - camera: Extracted camera name
              - camera_url: URL to camera page (if matched)
              - link: Full share link URL
    """
    # Fetch film and camera reference data from filmtypes.com
    film_types_dict = get_film_types_from_filmtypes_com()
    cameras_dict = get_cameras_from_filmtypes_com()

    # Filter for public albums only (marked with "Public: True" in description)
    public_links = [
        link for link in shared_links
        if "Public: True" in link.get("album", {}).get("description", "")
    ]

    # Initialize result list
    immich_data = []

    # Process albums in phases with progress tracking
    with Progress(console=console) as progress:
        # Phase 1: Pull thumbnails for album covers
        thumb_task = progress.add_task(
            "[cyan]Pulling thumbnails...", total=len(public_links)
        )
        thumbnails = {}
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                # Get the asset ID for the album's thumbnail/cover image
                cover_asset_id = album.get("albumThumbnailAssetId")
                # Fetch thumbnail as base64 data URL
                cover_thumbnail = get_asset_thumbnail_data_url(
                    immich_server_url, immich_api_key, cover_asset_id
                )
                thumbnails[shared_link["key"]] = cover_thumbnail
            except Exception as error:
                console.print(f"[yellow]⚠[/yellow] Thumbnail error: {error}")
                thumbnails[shared_link["key"]] = None
            finally:
                progress.update(thumb_task, advance=1)

        # Phase 2: Match film and camera information to filmtypes.com
        match_task = progress.add_task(
            "[magenta]Matching film & camera types...", total=len(public_links)
        )
        matches = {}
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                description = album["description"]

                # Extract film stock from structured description format
                # Format: "Film Stock: [name] Development Notes: [notes]
                # Camera: [camera]"
                film_stock = (description.split("Film Stock:")[1]
                              .split("Development Notes:")[0]
                              .split("Camera:")[0].strip())
                film_type_url = find_matching_film_type(film_stock, film_types_dict)

                # Extract camera from structured description format
                camera = description.split("Camera:")[1].split("Lens:")[0].strip()
                camera_url = find_matching_camera(camera, cameras_dict)

                # Store matching results for this album
                matches[shared_link["key"]] = {
                    "film_stock": film_stock,
                    "film_type_url": film_type_url,
                    "camera": camera,
                    "camera_url": camera_url,
                }
            except Exception as error:
                console.print(f"[yellow]⚠[/yellow] Matching error: {error}")
                matches[shared_link["key"]] = {}
            finally:
                progress.update(match_task, advance=1)

        # Phase 3: Build final album data structures
        build_task = progress.add_task(
            "[green]Building album data...", total=len(public_links)
        )
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                description = album["description"]

                # Get pre-computed data for this album
                album_key = shared_link["key"]
                match_data = matches.get(album_key, {})
                thumbnail = thumbnails.get(album_key)

                # Build complete album data structure
                immich_data.append(
                    {
                        "name": album["albumName"].split(" (")[0],
                        # Remove any parenthetical info
                        "cover_thumbnail": thumbnail,
                        "description": description.split("Date Captured:")[0],
                        # Description before date
                        "date": parse_capture_date(description),
                        # Parse and format capture date
                        "film_stock": match_data.get("film_stock", ""),
                        "film_type_url": match_data.get("film_type_url"),
                        "camera": match_data.get("camera", ""),
                        "camera_url": match_data.get("camera_url"),
                        "link": f"{share_base_url}/{album_key}",
                        # Full share link
                    }
                )
            except (KeyError, IndexError, ValueError) as error:
                console.print(f"[yellow]⚠[/yellow] Skipping album: {error}")
            finally:
                progress.update(build_task, advance=1)

    # Return albums sorted by date (newest first)
    return sorted(immich_data, key=lambda x: x["date"], reverse=True)


def render_homepage(album_data, generated_at=None, template_dir="./templates/"):
    """
    Render the album data into HTML using Jinja2 template.

    Takes the processed album data and renders it into a complete HTML page
    using the Jinja2 template engine. Shows progress during template loading
    and rendering phases.

    Args:
        album_data (list): List of album dictionaries from build_album_data()
        generated_at (datetime): Timestamp for when the page was generated
        template_dir (str): Directory containing the template files

    Returns:
        str: Complete HTML content for the homepage
    """
    # Set up Jinja2 environment with template directory
    env = Environment(loader=FileSystemLoader(template_dir))

    # Render template with progress tracking
    with Progress(console=console) as progress:
        task = progress.add_task("[blue]Rendering template...", total=2)

        # Load the template file
        template = env.get_template("template.html")
        progress.update(task, advance=1)

        # Prepare template variables
        generated_at = generated_at or datetime.now()
        date_string = generated_at.strftime("%Y-%m-%d %H:%M:%S")
        html_data = {"album_data": album_data, "date": date_string}

        # Render the template with album data
        html_output = template.render(input_data=html_data)
        progress.update(task, advance=1)

    return html_output


def write_homepage(output_text, output_path=DEFAULT_OUTPUT_PATH):
    """
    Write the rendered HTML content to a file.

    Saves the generated HTML homepage to the specified output file path.

    Args:
        output_text (str): Complete HTML content from render_homepage()
        output_path (str): File path where the HTML should be written
    """
    with open(output_path, mode="w") as output_file:
        output_file.write(output_text)


def main():
    """
    Main entry point for the Photo Server Homepage Generator.

    Orchestrates the complete workflow:
    1. Load configuration from environment variables
    2. Fetch shared links from Immich server
    3. Process albums with film/camera matching and thumbnails
    4. Render HTML homepage using Jinja2 template
    5. Write output file and display completion summary

    Uses Rich library for enhanced terminal output with progress bars,
    colored text, and formatted panels.
    """
    # Display application header
    console.print(Rule("[bold]Photo Server Homepage Generator[/bold]", style="cyan"))

    # Load configuration from environment variables
    console.print("\n[bold]Configuration[/bold]")
    immich_server_url, immich_api_key = load_config()
    console.print(Rule(style="dim"))

    # Fetch all shared links from Immich server
    console.print("\n[bold]Fetching Data[/bold]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Getting shared links from Immich...", total=None)
        shared_links_list = get_all_shared_links(immich_api_key, immich_server_url)

    console.print(f"[green]✓[/green] Found [bold]{len(shared_links_list)}"
                  "[/bold] shared links")
    console.print(Rule(style="dim"))

    # Process albums: fetch thumbnails, match film/camera types, build data structures
    console.print("\n[bold]Processing Albums[/bold]")
    sorted_immich_data = build_album_data(
        shared_links_list,
        immich_server_url=immich_server_url,
        immich_api_key=immich_api_key,
    )

    console.print(f"[green]✓[/green] Processed [bold]{len(sorted_immich_data)}"
                  "[/bold] public albums")
    console.print(Rule(style="dim"))

    # Render the HTML homepage using Jinja2 template
    console.print("\n[bold]Rendering[/bold]")
    output_text = render_homepage(sorted_immich_data)
    console.print("[green]✓[/green] Homepage rendered")

    # Write the rendered HTML to output file
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Writing index.html...", total=None)
        write_homepage(output_text)
    console.print("[green]✓[/green] Homepage written to disk")
    console.print(Rule(style="dim"))

    # Display completion summary in a formatted panel
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_row("[bold]Shared Links:[/bold]", str(len(shared_links_list)))
    summary_table.add_row("[bold]Public Albums:[/bold]", str(len(sorted_immich_data)))
    summary_table.add_row("[bold]Output:[/bold]", DEFAULT_OUTPUT_PATH)
    summary_table.add_row("[bold]Generated:[/bold]",
                          datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    console.print(
        Panel(
            summary_table,
            title="[bold green]✓ Completion Summary[/bold green]",
            border_style="green",
        )
    )
    console.print("")


if __name__ == "__main__":
    main()
