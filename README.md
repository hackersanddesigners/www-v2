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

### .env, settings.toml

this project needs two settings files to function:

- `.env`
- `sttings.toml`

#### .env

rename `env.sample` to `.env` and fill out the file using this reference:

- `ENV`: set either `dev` or `prod`; this is mostly used to decide if using a local certificate when doing HTTP operation or not
- `SERVER_IP`: set a host for the `server.py` function => eg. `localhost`
- `SERVER_PORT`: set a port number for the `server.py` function (ergo, opening a port to listen to UDP messages from the MediaWiki instance) => eg. `1331`
- `WIKI_DIR`: path to static HTML output folder. choose a name for it (eg. `wiki`), create it, and set its name here
- `ASSETS_DIR`: path to static folder: eg. CSS, JS, images
- `MEDIA_DIR`: path for the media directory of WIKI_DIR => eg => `<WIKI_DIR>/assets/media`
- `BASE_URL`: base API URL path => eg. for local setup: `http://localhost/api.php?`; for an online wiki `https://wikixyz.tld/api.php?`

we create bot user to help programmatically creating, editing or deleting a wiki article. get credentials by visting the `Special:BotPasswords` page of your wiki. then:

- `BOT_USR`: use lgname
- `BOT_PWD`: use lgpassword

- `LOCAL_CA`: see below under *local certificate*
- `SEMAPHORE`: number of max operations happening at the same time when (mostly) doing async HTTP call. above this number the Python interpreter will throw an error. a good number is between 150-175, try and see what works.

#### local certificate

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

there is a CLI program at `cli.py` to run common operations. currently available commands are:

- `server`: starts a local server and listen to specified port at UDP messages from the MediaWiki instance; whenever a new message comes in, it runs the `app/build_article.py` functions to parse and save a new version of the received article to disk

- `build-wiki`: rebuilds the entire wiki, where by entire it's meant the list of articles with specific categories defined in `settings.toml`; it runs `app/build-article.py` to do so
  - `build-wiki --index-only`: rebuild only index pages, eg the one set in `settings.toml`; this is a faster way to build these pages as it does not parse each article

- `make-article`: helper function to trigger a change in the MediaWiki instance, instead of manually loggin in to the MW editor and commit a change. the command takes two arguments: `PageTitle` and type of operation (`edit`, `delete`); the `edit` operation creates a new article if it does not exist yet.

to run a local web-server in order to browse the `wiki` folder, you can do:

- `uvicorn app.main:app --reload`
