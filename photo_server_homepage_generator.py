
from jinja2 import Environment, FileSystemLoader

data = {"items": ["apple", "banana", "cherry"]}


def main():

    # Set up the Jinja2 environment to load templates from the current directory
    env = Environment(loader=FileSystemLoader('./templates/'))

    # Load the template
    template = env.get_template('template.html')

    # render data in jinja template
    demoText = template.render(data)

    # print(inviteText)
    with open(f"index.html", mode='w') as f:
        f.write(demoText)


if __name__== "__main__":
    main()
