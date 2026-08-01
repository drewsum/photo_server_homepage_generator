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

The package expects two Jinja2 templates in the `templates/` directory:

- `template.html` — the homepage. Receives `input_data` with:
  - `album_data` — a list of album dictionaries, each including a `page_url`
    pointing at that album's generated page
  - `date` — the homepage generation timestamp
- `album.html` — a per-album page. Receives `input_data` with:
  - `album` — a single album dictionary, including an `assets` list of
    `{filename, thumbnail_url, original_url, size_class}` for every image in
    the album
  - `date` — the page generation timestamp

Each album dictionary includes:

- `name`, `description`, `date`, `film_stock`, `film_type_url`, `camera`,
  `camera_url`, `cover_thumbnail`
- `link` — the original Immich shared-link URL
- `page_url` — the relative path to the generated album page (e.g.
  `albums/<key>.html`)
- `assets` — the album's images, each with a public `thumbnail_url` and
  `original_url` built from the Immich server URL and the shared link's key
  (Immich serves shared assets publicly via a `?key=` query parameter, so no
  API key is required to *view* them), plus a randomly assigned `size_class`
  (`size-sm`/`size-md`/`size-lg`) used to vary each tile's size in the album
  page's mosaic-style image grid. The asset *list* itself is fetched via the
  authenticated `/api/search/metadata` endpoint filtered by album ID, not
  the shared-link detail endpoint — Immich's `/api/shared-links/me` and
  `/api/albums/{id}` responses were observed returning an empty `assets`
  array for albums created before an Immich upgrade, even though the
  assets themselves were intact and the album's `assetCount` was correct;
  searching by album ID doesn't have that issue
- `metadata` — every `Key: Value` field found in the album description
  (Lens, F number, Focal Length, Flash, Development Notes, Date Scanned,
  etc.), as `{label, value, url}` rows for the album page's info table. New
  fields in the description show up automatically; `Film Stock` and
  `Camera` rows get `url` set to the matched filmtypes.com link, and
  `Date Captured` is omitted since it's already shown separately
- `newer_album` / `older_album` — `{name, filename}` of the chronologically
  adjacent album (by capture date), or `None` at either end of the list.
  `filename` (not `page_url`) is deliberate: album pages all live flatly in
  `albums/`, so a link from one to another only needs the target's
  filename, not the `albums/`-prefixed path the homepage uses

Both pages are responsive (the homepage's album table becomes a stacked
card list on narrow screens) and the album page includes a JS lightbox:
clicking a thumbnail opens the full-size original in an overlay with
prev/next buttons, arrow-key and click-outside-to-close support, instead of
navigating away from the page.

## Output

The generated homepage is written to `/output/index.html` by default, with one
HTML page per album written beneath `/output/albums/<key>.html`. Album page
links on the homepage, and the "back to albums" link on each album page, are
relative, so the whole `/output` directory can be served as a static site.
You can configure the output path in the package or container runtime if needed.
