
from jinja2 import Environment, FileSystemLoader

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

    # render data in jinja template
    demoText = template.render(album_data=data)

    # print(inviteText)
    with open(f"index.html", mode='w') as f:
        f.write(demoText)


if __name__== "__main__":
    main()
