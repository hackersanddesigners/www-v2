# Architecture

The website is built around the following idea:

- listening to MediaWiki Recent Changes APIs
- output one or more HTML files based on the given article change

We rely on the running MediaWiki instance to server image, audio and video files.

The website has two modalities: 

- *listening mode*, automatic; eg. `python cli.py server`
- *build mode*, manual; eg. `python cli.py build-article <PageTitle>`


## Diagram workflow example

An example diagram of the website workflow when updating an article:

(this is running in *listening-mode*)

- we receive a message and decide what to do in `server` (`app/server.py`):
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

If the operation is of type `delete`, another set of steps are used to remove the article and update every other bit of the website — same for operation `move`.

## Codebase outline


### User Interface

- `cli.py`: this command is used as an entrypoint into the codebase; everyday command to work with the website and do maintenance.

### Core

- `app/*`: everything actually lives in here.

#### Build

This set of functions handle the (re-)build operations — from the granular need of building a single article, to the macro need of building the whole website.

Each of this function is wired up in the CLI interface.

- `build_article.py`
- `build_category_index.py`
- `build_front_index.py`
- `build_wiki.py`

## gg

- `main.py`
- `server.py`

### xx

- `fetch.py`
- `parser.py`

- `file_ops.py`


  
- `read_settings.py`
- `copy_assets.py`
- `log_to_file.py`
- `pretty_json_log.py`
  
- `make_change_in_wiki.py`
  
### views

This set of functions transform the data prepared from the fetching and parsing operations, into the HTML template.
  
- `views/*`
  - `template_utils.py`: various useful functions; many of this are used directly in the jinja templates by way of the `|` pipe operator. See [jinja's custom filters](https://jinja.palletsprojects.com/en/3.0.x/api/?highlight=environment#writing-filters) as well as how they are [registered in FastAPI via Starlette](https://www.starlette.io/templates/#jinja2templates). We do this in `app/main.py`.
  - `views.py`: each article template has its preparing function in here.
  - `templates/*`
	- `<template>.html`: see [Jinja's docs](https://jinja.palletsprojects.com/en/3.1.x/templates/#include), [FastAPI templates](https://fastapi.tiangolo.com/advanced/templates/) and [Starlette's templates](https://www.starlette.io/templates/#jinja2templates).
	- `partials`: we use partials for re-usable HTML snippets, see [Jinja's include](https://jinja.palletsprojects.com/en/3.1.x/templates/#include).
		- `<snippet>.html`
  
