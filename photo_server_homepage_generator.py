
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime, date, time
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


def main():

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
