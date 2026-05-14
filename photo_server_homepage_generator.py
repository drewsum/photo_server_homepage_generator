import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

DEFAULT_OUTPUT_PATH = "/output/index.html"
DEFAULT_SHARE_BASE_URL = "https://photos.drewsum.us/share"


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
        print(f"Found server URL env variable: {immich_server_url}")
    else:
        print("Could not find IMMICH_SERVER environment variable, please add it!")

    if immich_api_key is not None:
        print("Found Immich API env variable")
    else:
        print("Could not find IMMICH_API_KEY environment variable, please add it!")

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


def build_album_data(shared_links, share_base_url=DEFAULT_SHARE_BASE_URL):
    immich_data = []
    for shared_link in shared_links:
        try:
            album = shared_link["album"]
            description = album["description"]
            if "Public: True" not in description:
                continue

            immich_data.append(
                {
                    "name": album["albumName"].split(" (")[0],
                    "description": description.split("Date Captured:")[0],
                    "date": parse_capture_date(description),
                    "film_stock": description.split("Film Stock:")[1]
                    .split("Development Notes:")[0]
                    .split("Camera:")[0],
                    "camera": description.split("Camera:")[1].split("Lens:")[0],
                    "link": f"{share_base_url}/{shared_link['key']}",
                }
            )
        except (KeyError, IndexError, ValueError) as error:
            print(error)

    return sorted(immich_data, key=lambda x: x["date"], reverse=True)


def render_homepage(album_data, generated_at=None, template_dir="./templates/"):
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("template.html")
    generated_at = generated_at or datetime.now()
    date_string = generated_at.strftime("%Y-%m-%d %H:%M:%S")
    html_data = {"album_data": album_data, "date": date_string}

    return template.render(input_data=html_data)


def write_homepage(output_text, output_path=DEFAULT_OUTPUT_PATH):
    with open(output_path, mode="w") as output_file:
        output_file.write(output_text)


def main():
    immich_server_url, immich_api_key = load_config()

    # get all shared links from immich server
    shared_links_list = get_all_shared_links(immich_api_key, immich_server_url)
    for shared_link in shared_links_list:
        print(f"found shared link id: {shared_link['id']}")

    sorted_immich_data = build_album_data(shared_links_list)
    output_text = render_homepage(sorted_immich_data)
    print("Rendered jinja text")

    write_homepage(output_text)
    print("Generated index.html")


if __name__ == "__main__":
    main()
