
from jinja2 import Environment, FileSystemLoader
import os
import requests
from datetime import datetime
import json
from dotenv import load_dotenv

def get_all_shared_links(api_key, url):

    payload = {}
    headers = {
        'Accept': 'application/json',
        'x-api-key': api_key
    }
    response = requests.request("GET", url+"/api/shared-links", headers=headers, data=payload)
    
    return response.json()

def main():

    try:
        load_dotenv()
        print("Found and loaded .env file")
        immich_server_url = os.getenv("IMMICH_SERVER")
        if immich_server_url is not None:
            print("Found server URL env variable: {}".format(immich_server_url))
        else:
            print("Could not find IMMICH_SERVER environment variable, please add it!")
        immich_api_key = os.getenv("IMMICH_API_KEY")
        if immich_api_key is not None:
            print("Found Immich API env variable: {}".format(immich_api_key))
        else:
            print("Could not find IMMICH_API_KEY environment variable, please add it!")
    except:
        print("Could not find .env file, checking windows variables")
        # try to find server environment variables
        immich_server_url = os.getenv("IMMICH_SERVER")
        if immich_server_url is not None:
            print("Found server URL env variable: {}".format(immich_server_url))
        else:
            print("Could not find IMMICH_SERVER environment variable, please add it!")
        immich_api_key = os.getenv("IMMICH_API_KEY")
        if immich_api_key is not None:
            print("Found Immich API env variable: {}".format(immich_api_key))
        else:
            print("Could not find IMMICH_API_KEY environment variable, please add it!")

    # get all shared links from immich server
    shared_links_list = get_all_shared_links(immich_api_key, immich_server_url)
    for shared_link in shared_links_list:
        print(f"found shared link id: {shared_link['id']}")

    # Set up the Jinja2 environment to load templates from the current directory
    env = Environment(loader=FileSystemLoader('./templates/'))

    # Load the template
    template = env.get_template('template.html')

    # Create a datetime object
    now = datetime.now()

    # Format the datetime object into a datestring
    date_string = now.strftime("%Y-%m-%d %H:%M:%S") 

    # append found immich shared links into data structure for jinja template
    immich_data = []
    for shared_link in shared_links_list:
        if "Public: True" in shared_link['album']["description"]:
            immich_data.append(
                {
                    "name" : shared_link['album']["albumName"].split(" (")[0],
                    "description" : shared_link['album']["description"].split("Date Captured:")[0],
                    "date" : datetime.strptime((shared_link['album']["description"].split("Date Captured:")[1].split("Date Scanned:")[0]).strip("\n").strip(" ").replace("/", ""), "%m%d%Y").strftime("%Y-%m-%d"),
                    "film_stock" : shared_link['album']["description"].split("Film Stock:")[1].split("Development Notes:")[0].split("Camera:")[0],
                    "camera" : shared_link['album']["description"].split("Camera:")[1].split("Lens:")[0],
                    "link" : "https://photos.drewsum.us/share/" + shared_link['key']
                }
            )


    # sort by capture date
    sorted_immich_data = sorted(immich_data, key=lambda x: x['date'], reverse=True)

    # create data for template
    html_data = {
        "album_data": sorted_immich_data, 
        "date": date_string
        }

    # render data in jinja template
    output_text = template.render(input_data=html_data)

    print("Rendered jinja text")

    with open(f"/output/index.html", mode='w') as f:
        f.write(output_text)
        print("Generated index.html")
        

if __name__== "__main__":
    main()
