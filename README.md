# hackersanddesigners.nl v2

## setup

we're using python 3.10 at the time of writing (check `.python-version`). we're also using a nix-based program (devenv) to create a complete dev environment for the project. you don't have to use it. we provide a classic `requirements.txt` to install packages with `pip`.

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

## intro

this is a program to export data from MediaWiki into a mostly static website.

the underlying idea is to make it easier to archive and distribute the website in a more accessible format to work with: 

- we export each article into its Mediawiki plain text syntax
- add it to a git repo
- distribute the repo across computers

we also save to HTML the article content so to have less breaking states of the website, and distribute that into the git repo too. we include images and other files part of each article.

once we have all the wiki data articles out we can do, anything!

## details

**this is still in progress!**

- a static site generator that creates a new page whenever a change is done on the wiki (using [wgRCFeeds](wgRCFeedshttps://www.mediawiki.org/wiki/Manual:%24wgRCFeeds) UDP messaging)
- a FastAPI app providing a search interface to display results from the wiki, and other sources

structure:

  - `<h&d.nl>` (frontpage as `static-page.html`?)
  - `<h&d.nl/p/static-page.html>`
  - `<h&d.nl/s/<search-query>`
  
to run this on a MediaWiki instance, add the following to `LocalSettings.php` (`RCFeeds` example):

```
$wgRCFeeds['had-py'] = array(
    'formatter' => 'JSONRCFeedFormatter',
    'uri' => 'udp://localhost:1338',
    'add_interwiki_prefix' => false,
    'omit_bots' => true,
);
```


then run `python app/server.py` and make a change to a wiki article using MW web interface: a message should appear on the terminal, detecting which page has been modified.

## mediawiki

a local instance of mediawiki must be run, in order to have this software working correctly.

check this repo to set up a MW instance: <https://github.com/hackersanddesigners/hd-mw>

## Local dev setup and TLS certificates

install [mkcert](https://github.com/FiloSottile/mkcert) or similar to create a local certificate.

for mkcert:

```
# if it is the first time, install it
mkcert -install

# then make local CA for current website, for instance
mkcert hd-v2.nl
```

this will create two files in the current folder:

- `hd-v2.nl-key.pem`
_ `hd-v2.nl.pem`

add an entry to `.env` with:

```
LOCAL_CA=hd-v2.nl.pem
```

if you have another name for your local certificate instead of `hd-v2`, use that name for the `.env` entry.

after this you can use https also in the dev environment while using this codebase!


## commands

currently available commands:

- `python app/server.py`: starts a local server and listen to specified port at UDP messages from the MediaWiki instance; whenever a new message comes in, it runs the `app/build_article.py` functions to parse and save a new version of the received article to disk
- `python app/build_wiki.py`: rebuilds the entire wiki, where by entire it's meant the list of articles with specific categories defined in `settings.toml`; it runs `app/build-article.py` to do so
  - `python app/build_wiki.py --index=true`: rebuild only index pages, eg the one set in `settings.toml`; this is a faster way to build these pages as it does not parse each article
- `python app/make_change_in_wiki.py`: helper function to trigger a change in the MediaWiki instance, instead of manually loggin in to the MW editor and commit a change. the command takes two arguments: `PageTitle` and type of operation (`edit`, `delete`); the `edit` operation creates a new article if it does nnot exist yet. for example:

    - `python app/make_change_in_wiki.py "ToolExample" edit`

- `uvicorn app.main:app --reload`: run local server to browse HTML in `/wiki`
