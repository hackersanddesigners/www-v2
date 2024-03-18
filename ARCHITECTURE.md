# Architecture

## Intro

This software runs as the following:

- a server listening to any change taking place in a MediaWiki instance, by using MW's [wgRCFeeds](https://www.mediawiki.org/wiki/Manual:%24wgRCFeeds) UDP messaging protocol
- at any change of an article (create, edit, move, delete), we do update the given article accordingly (eg, create, edit, move or delete it)
- each article is saved to disk as static HTML
- the list of categories defined in `settings.toml`, as well as the frontpage (which combines upcoming events, articles with category `Highlight` and the H&D article) are also generated as static HTML, and kept up-to-date whenever any of the involved articles has been changed
- a FastAPI app provides a search interface to display results from the wiki

We rely on the running MediaWiki instance to serve image, audio and video files. We just produce HTML files.

## Routing

Website routing structure:

- `<h&d.nl>` (frontpage, `index.html`)
- `<h&d.nl/<article.html / category.html>`
- `<h&d.nl/<search-query>`

## RecentChanges APIs

See: 

- [API:RecentChanges](https://www.mediawiki.org/wiki/API:RecentChanges)
- [wgRCFeeds](https://www.mediawiki.org/wiki/Manual:%24wgRCFeeds)

We opted for UPD messaging instead of using redis, because redis is one more dependency. Actually, only because André likes UDP and its approach to not check at all if the data sent has been received — just keep sending more data.

An example of the `wgRCfeeds` config block, commented:

```
$wgRCFeeds['exampleirc'] = array(
    'formatter' => 'JSONRCFeedFormatter',
    'uri' => 'udp://localhost:1338',
    'add_interwiki_prefix' => false,
    'omit_bots' => false,
    'omit_anon' => false, # to detect wiki changes from scripted API requests
    'omit_minor' => false,
    'omit_patrolled' => false
);
```

- `exampleirc`: this is just a label, name it anything you like
- `formatter`: we stick to JSON over XML because of popularity
- `uri`: set a port value that's not taken already in your host machine
- `add_interwiki_prefix`: non-relevant for us, we don't use this for IRC bots
- `omit_bots`: false since we use bots in development, and we want the change done by the bot to trigger this UDP messaging to ping our listening `server.py`
- `omit_anon`: false, same reasoning as above (omit_bots)
- `omit_minor`: false. every change is relevant for us, a chance to trigger a UDP message (useful if we want to do a "ghost edit" — add a white space in the article, just to trigger a new change and re-build the article as HTML in our website)
- `omit_patrolled'`: false. don't skip a change

## Interaction

The website has two modalities: 

- *listening mode*, automatic; eg. `python cli.py server`
- *build mode*, manual; eg. `python cli.py build-article <PageTitle>`

Tendentially you want to run one process as listening mode and in parallel run other commands through the manual mode. The manual commands can be run as programmatic actions as well, eg. running the frontpage build command via a timer to keep the website frontpage up-to-date (for instance once a day).

See the *system config* section in the [README](./README.md) for more details and examples.

## Diagram workflow example

An example diagram of the website workflow when updating an article:

(this is running in *listening-mode*)

- we receive a message and decide what to do with it in `server` (`app/server.py`):
  - check which type of operation took place (new article, edit, move, deletion, restore)
  - filter out some type of unwanted articles (eg. *Concept:*, *Special:*)
  - run `make_article` (`app/build_article.py/make_article`) by passing the article title to it
  - `make_article` runs:
	-  `fetch_article` to get all the article data from the MediaWiki APIs (`app/fetch.py/fetch_article`)
	- parse the data with `parser.py` (`app/parser.py`)
	- return a dictionary with all the prepared data
  - back in `server`, we then do some checks to eventually update other areas of the website based on the update of this article:
	- check if we need to remove any article's traces across the website with `remove_article_traces` (`app/build_article.py/remove_article_traces`)
	- update the given article's category index pages `update_categories` (`app/update_category_index.py/update_categories`)
	- update every article backlinks in other article pages `update_backlinks` (`app/build_article.py/update_backlinks`)
	- check if this article is used in the frontpage, if so update frontpage `build_front_index` (`app/build_front_index.py/build_front_index`)
    - at last save this article to disk `save_article` (`app/build_article.py/save_article`)

If the operation is of type `delete`, another set of steps are used to remove the article and update every other bit of the website — same for operation `move`, `restore` and so on.

## Codebase outline

### User Interface

- `cli.py`: this command is used as an entry point into the codebase; everyday commands to work with the website and do maintenance.

### Core

- `app/*`: everything actually lives in here.

#### Build

This set of functions handle the (re-)build operations — from the granular need of building a single article, to the macro need of building the whole website.

Each of this function is wired up in the CLI interface.

- `build_article.py`: build specific article; requires `fetch.py`
- `build_category_index.py`: build specific category index page; requires `fetch.py` and `build_article.py`
- `build_front_index.py`: build website frontpage; requires `fetch.py` and `build_article.py`
- `build_wiki.py`: build entire website; requires `build_category_index`, etc.

#### Server

There are two server functions: the former runs a web-server through FastAPI (which we need primarily for the search route); the latter is the server listening to the UPD messaging coming from the Mediawiki APIs.

- `main.py`: check [FastAPI](https://fastapi.tiangolo.com/advanced/templates/) and [Starlette](https://www.starlette.io/templates/#jinja2templates)
- `server.py`: check [wgRCFeeds](https://www.mediawiki.org/wiki/Manual:$wgRCFeeds)

#### Data Manipulation

These three functions do a lot of work between the MediaWiki APIs and the creation of our HTML files.

- `fetch.py`: HTTP API calls to MediaWiki
- `parser.py`: shaping of the final article form via HTML manipulation, bits of data extraction from it as well as parsing of other data received from the fetch operations
- `file_ops.py`: looking at and inside HTML files saved on disk and / or save new version of HTML files to disk

#### Helper Functions

These functions do small things each on their own, from reading the file settings to log data in a specific format.
  
- `read_settings.py`: self-explanatory
- `copy_assets.py`: copy static assets (CSS and JS files) from FastAPI directory (`./static`) to the HTML output directory (eg `./<WIKI_DIR>/static`)
- `log_to_file.py`: write any logged message to the specified file in `./logs/<file>`; useful when re-building the entire website and not having to scroll back up through the terminal output
- `pretty_json_log.py`: helper function to format a print statement with JSON data
- `make_change_in_wiki.py`: set of few functions to make changes in a given MediaWiki article without having to go though the web interface each time; it just supports the creation + edit and delete of an article, not the move / rename of it (due to MediaWiki's APIs limitations / specific requirements)
  
#### Views

This set of functions transform the data prepared from the fetching and parsing operations, into the HTML template:
  
- `views/*`
  - `template_utils.py`: various useful functions; many of these are used directly in the Jinja templates by way of the `|` pipe operator. See [Jinja's custom filters](https://jinja.palletsprojects.com/en/3.0.x/api/?highlight=environment#writing-filters) as well as how they are [registered in FastAPI via Starlette](https://www.starlette.io/templates/#jinja2templates). We do this in `app/main.py`.
  - `views.py`: each article template has its preparing function in here.
  - `templates/*`
	- `<template>.html`: see [Jinja's docs](https://jinja.palletsprojects.com/en/3.1.x/templates/#include), [FastAPI templates](https://fastapi.tiangolo.com/advanced/templates/) and [Starlette's templates](https://www.starlette.io/templates/#jinja2templates).
	- `partials`: we use partials for re-usable HTML snippets, see [Jinja's include](https://jinja.palletsprojects.com/en/3.1.x/templates/#include).
		- `<snippet>.html`
  
## Closing notes

Don't fight MediaWiki's APIs!

MediaWiki's APIs are not particularly well done, or they depend on MW's internals which — through their APIs — don't appear to be that malleable and composable. Therefore, keep in mind that often times we had to play around many limitations simply by running several HTTP API call in a row, and compose the data into one decent shape on our side. 
