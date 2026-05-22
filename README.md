# photo_server_homepage_generator

Generate HTML for serving on nginx from Immich shared links.

## Overview

This package collects public shared album data from an Immich server, builds album metadata, and renders an HTML homepage using a Jinja2 template.

It is designed to run in a containerized environment and write the generated site to a configured output path.

## Requirements

- Python 3.9 or higher
- `requests`
- `python-dotenv`
- `Jinja2`
- A valid `.env` file with Immich server settings

## Deployment

When deployed, this package is typically run inside a Docker container.

The container must include:

- the application code
- the `templates/template.html` file
- a writable output location for `index.html`
- an `.env` file containing the Immich server configuration

## Within Truenas Scale:

The container can be built from within the Truenas Scale shell via docker file. Run `sudo docker build -t photo-home-page-gen .`

Then, set up a cron within truenas scale, running this bash command to run the container: `sudo docker run --rm --volume /mnt/drewpool/drewset/photo-server-landing-page:/output photo-home-page-gen`

This will run the container and mount the container's output folder within the container to /mnt/drewpool/drewset/photo-server-landing-page, which is where an nginx server is looking for html to serve

## Environment variables

The application reads the following variables from `.env`:

- `IMMICH_SERVER` — the base URL of your Immich server (for example, `https://immich.example`)
- `IMMICH_API_KEY` — the API key used to authenticate requests to Immich

Example `.env` file:

```env
IMMICH_SERVER=https://immich.example
IMMICH_API_KEY=your-api-key-here
```

## Usage

### Local development

Install the package and dependencies:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install -e .
```

Run the package manually:

```bash
python -m photo_server_homepage_generator
```

### Running tests

```bash
python -m pytest
```

## Template

The package expects a Jinja2 template at `templates/template.html`.
The template receives `input_data` with:

- `album_data` — a list of album dictionaries
- `date` — the homepage generation timestamp

## Output

The generated homepage is written to `/output/index.html` by default.
You can configure the output path in the package or container runtime if needed.
