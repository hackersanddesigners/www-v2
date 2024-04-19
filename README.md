# hackersanddesigners.nl v2

## setup

we're using python 3.10 at the time of writing (check `.python-version`). we're also using a nix-based program (devenv) to create a complete dev environment for the project. you don't have to use it. we provide a classic `requirements.txt` to install packages with `pip`.

we also use [rigprep](https://github.com/BurntSushi/ripgrep) (`rg`) to search across the `WIKI_DIR` (the folder with the static HTML articles fetched from the MediaWiki). please install ripgrep if it's missing from your system — if missing, you'll get an error in the terminal fro the website telling the `rg` binary was not found.

### devenv

if you're using `devenv`, do the following:

- make sure to install it first, [see instructions](https://devenv.sh/getting-started/)
- `devenv shell`

### virtual environment

if you want to stick to Python's standard tools, then:

- make a new virtual environment: `python3 -m venv env`
- activate virtual environment: `source env/bin/activate`

### packages

to install all packages do:

- try: `python3 -m pip install -r requirements.txt`
- else, make sure to upgrade pip: `python3 -m pip install --upgrade pip` and try again with the above command

whenever you install a new package with `pip`, update the requirements list with:

- `pip freeze > requirements.txt`

### systemd config

the software is controlled through some systemd unit files (you can inspect them under `./systemd`):

- `hd-www-frontend.service`: runs the server (handling routes, redirects, etc)
- `hd-www-udp.service`: runs the UDP server which listen to the MediaWiki instance sending messages whenever an article is created / modified / deleted

the above two systemd services are crucial for the functioning of the website.

there are two more systemd files that acts as a cronjob-like service. these are used to keep the frontpage up-to-date on a daily basis — necessary given that the frontpage is automatically updated only when any of the articles that it displays has received an update; so in cases when nothing changes for days, the upcoming events section might get out of date.

these two systemd services are:

- `hd-www-bg-task.service`: to setup the necessary command to run on a given period of time
- `hd-www-bg-task.timer`: to set the actual timer

## everyday usage

there are two ways to use this software:

1. run the local server that listens to MediaWiki UDP messages
2. (re-) build part of, or the entire wiki, at once

first of all run the local MediaWiki instance ([from this repo](https://github.com/hackersanddesigners/mw-fork)):

- open a terminal, `cd` to the MW repo and run `devenv up`

then, if wanting to do 1:

- open another terminal and `cd` into this repo
- run `source env/bin/activate` (or `devenv shell` if you use devenv)
- then run `python cli.py server` to listen to the MW changes

otherwise, if interested in 2:

- `cd` into this repo and activate the environment
- run `python cli.py build-article` or any other command to build the entire wiki, a specific category page, the frontpage, etc.

type `python cli.py --help` for a list of all the options.

### scripts

there are two Python helper scripts to lint and format code:

- the former runs [flake8](https://flake8.pycqa.org/en/latest/index.html) and reports you a list of suggestions;
- the latter runs [isort](https://pycqa.github.io/isort/) and [black](https://black.readthedocs.io/en/stable/index.html) to update the codebase by (1) re-sorting the list of imports at the top of a file, and (2) rewriting code in a specific style (eg using single quote, keeping correct whitespace between lines of code, etc).

you can run them manually by simple shell invocation:

```
./scripts/lint
./scripts/format
```

## intro

this program acts as a static site builder for a MediaWiki instance. we define in `settings.toml` the list of categories we use to fetch articles from the wiki, and output a folder of static HTML files.

a backend server, besides serving HTML files also run a search feature by interfacing with the MediaWiki APIs.

originally the idea was to export the MediaWiki's wikitext beside the HTML, but the extra complexity added to handle this while building a static website grew way bigger than imagined. so we took a step back and now rely on MediaWiki's APIs to retrieve data (article HTML, article metadata, working with images, etc.).

overall we still achieve the plan to generate a set of HTML files that can be easily backed up, parsed, re-generated, and so on.

## mediawiki

a local instance of MediaWiki must be run, in order to have this software working correctly.

check this repo to set up a MW instance: <https://github.com/hackersanddesigners/hd-mw>

then make sure to add the following to the `.env.php` file (`RCFeeds` example):

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

## local dev setup and TLS certificates

### .env, settings.toml

this project needs two settings files to function:

- `.env`
- `settings.toml`

#### .env

rename `env.sample` to `.env` and fill out the file using this reference:

- `ENV`: set either `dev` or `prod`; this is mostly used to decide if using a local certificate when doing HTTP operation or not
- `SERVER_IP`: set a host for the `server.py` function => eg. `localhost`
- `SERVER_PORT`: set a port number for the `server.py` function (ergo, opening a port to listen to UDP messages from the MediaWiki instance) => eg. `1331`
- `WIKI_DIR`: path to static HTML output folder. choose a name for it (eg. `wiki`), create it, and set its name here
- `ASSETS_DIR`: path to static folder: eg. CSS, JS, images
- `MEDIA_DIR`: path for the media directory of WIKI_DIR => eg => `<WIKI_DIR>/assets/media`
- `LOG_DIR`: set the directory where to write log files
- `BASE_URL`: base API URL path => eg. for local setup: `http://localhost/api.php?`; for an online wiki `https://wikixyz.tld/api.php?`

we create a bot user to help programmatically creating, editing or deleting a wiki article. get credentials by visiting the `Special:BotPasswords` page of your wiki. then:

- `BOT_USR`: use lgname
- `BOT_PWD`: use lgpassword

- `LOCAL_CA`: see below under *local certificate*
- `SEMAPHORE`: number of max operations happening at the same time when doing async HTTP call. above this number the Python interpreter will throw an error. a good number is between 150-175, try and see what works.

#### local certificate

install [mkcert](https://github.com/FiloSottile/mkcert) or similar to create a local certificate.

for mkcert:

```
# if it is the first time, install it
mkcert -install

# then make local CA for current website, for instance
mkcert hd-v2.nl
```

(you can use a different name for the certificate, eg `mkcert <name>`)

this will create two files in the current folder:

- `hd-v2.nl-key.pem`
_ `hd-v2.nl.pem`

add an entry to `.env` with:

```
LOCAL_CA=hd-v2.nl.pem
```

after this you can use https also in the dev environment while using this codebase!

#### settings.toml

this file mainly set website preferences, eg general wiki options:

- `wiki.stylespage`: name of stylesheet page
- `wiki.langs`: list of wiki languages, including default

- `wiki.frontpage.article`: which wiki article do we want to use for the website frontpage?
- `wiki.frontpage.category`: which category do we want to fetch for the articles displayed in the frontpage?

- `wiki.categories.<cat>`: sets a list of categories to define which wiki articles we want to display on the website. the `<cat>` is the actual MediaWiki category we want to use. then, each category has some more options:

  - `parse`: should we parse it (eg download every article of that category) or not; useful when working on the codebase to speed up parsing process if using `python cli.py build-wiki`, for instance
  - `nav`: should the category be displayed in the navigation
  - `index`: should we build a category index page for it
  - `fallback`: using this category as fallback, in case the wiki article has no matching category with the given list of categories
  - `label`: some categories in the wiki might be called something, and we might want to display them in a different way in the navigation, in the URL path, etc.

- `wiki.footer_links.<page>` (Conduct, Accessibility, Privacy Policy):
  - `nav`: add Conduct page to footer list of links
  - `label`: set label for the above link

`domain.canonical_url`: set default website URL
`domain.mw_url`: set URL to the running MediaWiki instance we want to work with

and specific plugin options:

- `tool-plugin.host_default`: which git hosting service fallback is the H&D MW Tool plugin using?
- `tool-plugin.host_default`: a dictionary of git hosting services the H&D MW Tool wants to use
- `tool-plugin.branch_default`: a list of branches to use when parsing information from the git repo set in the plugin; this works as a progressive list of fallback branch names

## commands

there is a CLI program at `cli.py` to run common operations. currently available commands are:

- `build-article` <PageTitle> <edit/delete>: helper function to trigger a change in the MediaWiki instance, instead of manually logging in to the MW editor and commit a change. the command takes two arguments: `PageTitle` and type of operation (`edit`, `delete`); the `edit` operation creates a new article if it does not exist yet, beside making a change to an existing wiki article.
- `build-frontpage`: builds the frontpage
- `build-category-index` <category>: builds the given category index page
- `build-wiki`: builds the entire wiki, where by entire it's meant the list of articles with specific categories defined in `settings.toml`
- `server`: starts a local server and listen to specified port at UDP messages from the MediaWiki instance
- `setup`: creates the necessary folders to run the website

start off by running `python cli.py --help` to see the available options.

to run a local web-server in order to browse the `wiki` folder, you can do:

- `uvicorn app.main:app --reload` or use `local-server.sh`.

## License

This repository is published under the [CC4r*](LICENSE) license.
