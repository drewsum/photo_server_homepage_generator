
from jinja2 import Environment, FileSystemLoader
import os
import requests
from datetime import datetime
import json

data = [
    {
        "name": "roll1",
        "description": "First roll of film yay!",
        "link": "www.google.com"
    },
    {
        "name": "roll2",
        "description": "My second roll of film",
        "link": "www.yahoo.com"
    }
]

def get_all_shared_links(api_key, url):

    payload = {}
    headers = {
        'Accept': 'application/json',
        'x-api-key': api_key
    }
    response = requests.request("GET", url+"/api/shared-links", headers=headers, data=payload)
    
    return response.json()

def main():

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
    for link in shared_links_list:
        print(f"found shared link id: {link['id']}")

    # Set up the Jinja2 environment to load templates from the current directory
    env = Environment(loader=FileSystemLoader('./templates/'))

    # Load the template
    template = env.get_template('template.html')

    # Create a datetime object
    now = datetime.now()

    # Format the datetime object into a datestring
    date_string = now.strftime("%Y-%m-%d %H:%M:%S") 

    # create data for template
    html_data = {
        "album_data": data, 
        "date": date_string
        }

    # render data in jinja template
    output_text = template.render(input_data=html_data)

    # print(inviteText)
    with open(f"index.html", mode='w') as f:
        f.write(output_text)

if __name__== "__main__":
    main()
