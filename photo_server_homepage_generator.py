import base64
import os
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
from rapidfuzz import fuzz
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.panel import Panel
from rich.table import Table

console = Console()

DEFAULT_OUTPUT_PATH = "/output/index.html"
DEFAULT_SHARE_BASE_URL = "https://photos.drewsum.us/share"

_thumbnail_cache = {}
_film_types_cache = None
_cameras_cache = None


def get_film_types_from_filmtypes_com():
    """Scrape all film types from filmtypes.com and return a dict of name -> url."""
    global _film_types_cache
    
    if _film_types_cache is not None:
        return _film_types_cache
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching film types from filmtypes.com...", total=None)
            response = requests.get("https://www.filmtypes.com/films", timeout=30)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find all film links - they appear to be in anchor tags with film names
        film_types = {}
        
        # Look for links in the format /films/film-name
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("/films/") and href != "/films":
                # Extract the film name from the link text
                film_name = link.get_text(strip=True)
                if film_name and film_name.lower() != "all film stocks":
                    # Normalize the film name
                    film_types[film_name] = f"https://www.filmtypes.com{href}"
        
        _film_types_cache = film_types
        console.print(f"[green]✓[/green] Loaded [bold]{len(film_types)}[/bold] film types")
        return film_types
    except Exception as error:
        console.print(f"[red]✗[/red] Could not fetch film types: {error}")
        return {}


def find_matching_film_type(film_stock, film_types_dict):
    """Use fuzzy matching to find the best matching film type URL."""
    if not film_stock or not film_types_dict:
        return None
    
    best_match = None
    best_score = 0
    threshold = 85  # Minimum similarity score
    
    for film_name, film_url in film_types_dict.items():
        # Use token_set_ratio for better matching with slightly different names
        score = fuzz.token_set_ratio(film_stock.lower(), film_name.lower())
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = film_url
    
    return best_match


def get_cameras_from_filmtypes_com():
    """Scrape all cameras from filmtypes.com and return a dict of name -> url."""
    global _cameras_cache
    
    if _cameras_cache is not None:
        return _cameras_cache
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Fetching cameras from filmtypes.com...", total=None)
            response = requests.get("https://www.filmtypes.com/cameras", timeout=30)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find all camera links - they appear to be in anchor tags with camera names
        cameras = {}
        
        # Look for links in the format /cameras/camera-name
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if href.startswith("/cameras/") and href != "/cameras":
                # Extract the camera name from the link text
                camera_name = link.get_text(strip=True)
                if camera_name and camera_name.lower() != "all film cameras":
                    # Normalize the camera name
                    cameras[camera_name] = f"https://www.filmtypes.com{href}"
        
        _cameras_cache = cameras
        console.print(f"[green]✓[/green] Loaded [bold]{len(cameras)}[/bold] cameras")
        return cameras
    except Exception as error:
        console.print(f"[red]✗[/red] Could not fetch cameras: {error}")
        return {}


def find_matching_camera(camera_name, cameras_dict):
    """Use fuzzy matching to find the best matching camera URL."""
    if not camera_name or not cameras_dict:
        return None
    
    best_match = None
    best_score = 0
    threshold = 85  # Minimum similarity score
    
    for cam_name, cam_url in cameras_dict.items():
        # Use token_set_ratio for better matching with slightly different names
        score = fuzz.token_set_ratio(camera_name.lower(), cam_name.lower())
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = cam_url
    
    return best_match


def get_all_shared_links(api_key, url):
    headers = {"Accept": "application/json", "x-api-key": api_key}
    response = requests.get(
        f"{url.rstrip('/')}/api/shared-links",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    return response.json()


def load_config():
    load_dotenv()
    immich_server_url = os.getenv("IMMICH_SERVER")
    immich_api_key = os.getenv("IMMICH_API_KEY")

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
    date_text = (
        description.split("Date Captured:")[1]
        .split("Date Scanned:")[0]
        .strip("\n")
        .strip(" ")
        .replace("/", "")
    )
    return datetime.strptime(date_text, "%m%d%Y").strftime("%Y-%m-%d")


def get_asset_thumbnail_data_url(server_url, api_key, asset_id):
    if not server_url or not api_key or not asset_id:
        return None

    cache_key = (server_url.rstrip("/"), asset_id)
    if cache_key in _thumbnail_cache:
        return _thumbnail_cache[cache_key]

    thumbnail_url = f"{server_url.rstrip('/')}/api/assets/{asset_id}/thumbnail"
    headers = {"Accept": "*/*", "x-api-key": api_key}

    try:
        response = requests.get(thumbnail_url, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "image/webp")
        encoded = base64.b64encode(response.content).decode("ascii")
        data_url = f"data:{content_type};base64,{encoded}"
        _thumbnail_cache[cache_key] = data_url
        return data_url
    except Exception as error:
            console.print(f"[yellow]⚠[/yellow] Could not fetch thumbnail for asset {asset_id}: {error}")


def build_album_data(
    shared_links,
    share_base_url=DEFAULT_SHARE_BASE_URL,
    immich_server_url=None,
    immich_api_key=None,
):
    film_types_dict = get_film_types_from_filmtypes_com()
    cameras_dict = get_cameras_from_filmtypes_com()
    
    # Filter for public albums first
    public_links = [
        link for link in shared_links 
        if "Public: True" in link.get("album", {}).get("description", "")
    ]
    
    immich_data = []
    
    with Progress(console=console) as progress:
        # Phase 1: Pull thumbnails
        thumb_task = progress.add_task(
            "[cyan]Pulling thumbnails...", total=len(public_links)
        )
        thumbnails = {}
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                cover_asset_id = album.get("albumThumbnailAssetId")
                cover_thumbnail = get_asset_thumbnail_data_url(
                    immich_server_url, immich_api_key, cover_asset_id
                )
                thumbnails[shared_link["key"]] = cover_thumbnail
            except Exception as error:
                console.print(f"[yellow]⚠[/yellow] Thumbnail error: {error}")
                thumbnails[shared_link["key"]] = None
            finally:
                progress.update(thumb_task, advance=1)
        
        # Phase 2: Match film and camera links
        match_task = progress.add_task(
            "[magenta]Matching film & camera types...", total=len(public_links)
        )
        matches = {}
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                description = album["description"]
                
                film_stock = description.split("Film Stock:")[1].split("Development Notes:")[0].split("Camera:")[0].strip()
                film_type_url = find_matching_film_type(film_stock, film_types_dict)
                
                camera = description.split("Camera:")[1].split("Lens:")[0].strip()
                camera_url = find_matching_camera(camera, cameras_dict)
                
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
        
        # Phase 3: Build album data
        build_task = progress.add_task(
            "[green]Building album data...", total=len(public_links)
        )
        for shared_link in public_links:
            try:
                album = shared_link["album"]
                description = album["description"]
                
                album_key = shared_link["key"]
                match_data = matches.get(album_key, {})
                thumbnail = thumbnails.get(album_key)
                
                immich_data.append(
                    {
                        "name": album["albumName"].split(" (")[0],
                        "cover_thumbnail": thumbnail,
                        "description": description.split("Date Captured:")[0],
                        "date": parse_capture_date(description),
                        "film_stock": match_data.get("film_stock", ""),
                        "film_type_url": match_data.get("film_type_url"),
                        "camera": match_data.get("camera", ""),
                        "camera_url": match_data.get("camera_url"),
                        "link": f"{share_base_url}/{album_key}",
                    }
                )
            except (KeyError, IndexError, ValueError) as error:
                console.print(f"[yellow]⚠[/yellow] Skipping album: {error}")
            finally:
                progress.update(build_task, advance=1)

    return sorted(immich_data, key=lambda x: x["date"], reverse=True)


def render_homepage(album_data, generated_at=None, template_dir="./templates/"):
    env = Environment(loader=FileSystemLoader(template_dir))
    
    with Progress(console=console) as progress:
        task = progress.add_task("[blue]Rendering template...", total=2)
        template = env.get_template("template.html")
        progress.update(task, advance=1)
        
        generated_at = generated_at or datetime.now()
        date_string = generated_at.strftime("%Y-%m-%d %H:%M:%S")
        html_data = {"album_data": album_data, "date": date_string}

        html_output = template.render(input_data=html_data)
        progress.update(task, advance=1)

    return html_output


def write_homepage(output_text, output_path=DEFAULT_OUTPUT_PATH):
    with open(output_path, mode="w") as output_file:
        output_file.write(output_text)


def main():
    console.print(Rule("[bold]Photo Server Homepage Generator[/bold]", style="cyan"))
    
    # Load configuration
    console.print("\n[bold]Configuration[/bold]")
    immich_server_url, immich_api_key = load_config()
    console.print(Rule(style="dim"))
    
    # Get shared links
    console.print("\n[bold]Fetching Data[/bold]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Getting shared links from Immich...", total=None)
        shared_links_list = get_all_shared_links(immich_api_key, immich_server_url)
    
    console.print(f"[green]✓[/green] Found [bold]{len(shared_links_list)}[/bold] shared links")
    console.print(Rule(style="dim"))
    
    # Build album data
    console.print("\n[bold]Processing Albums[/bold]")
    sorted_immich_data = build_album_data(
        shared_links_list,
        immich_server_url=immich_server_url,
        immich_api_key=immich_api_key,
    )
    
    console.print(f"[green]✓[/green] Processed [bold]{len(sorted_immich_data)}[/bold] public albums")
    console.print(Rule(style="dim"))
    
    # Render homepage
    console.print("\n[bold]Rendering[/bold]")
    output_text = render_homepage(sorted_immich_data)
    console.print("[green]✓[/green] Homepage rendered")
    
    # Write homepage
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Writing index.html...", total=None)
        write_homepage(output_text)
    console.print("[green]✓[/green] Homepage written to disk")
    console.print(Rule(style="dim"))
    
    # Summary panel
    summary_table = Table(show_header=False, box=None, padding=(0, 2))
    summary_table.add_row("[bold]Shared Links:[/bold]", str(len(shared_links_list)))
    summary_table.add_row("[bold]Public Albums:[/bold]", str(len(sorted_immich_data)))
    summary_table.add_row("[bold]Output:[/bold]", DEFAULT_OUTPUT_PATH)
    summary_table.add_row("[bold]Generated:[/bold]", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
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
