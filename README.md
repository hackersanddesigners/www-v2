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

### why are we parsing wiki articles instead of retrieving the HTML from MediaWiki's APIs?

because of the underlying intentions of the project, which is to exploit a MediaWiki feature built for real-time streaming purposes, to create a constant backup version of the wiki database into plain-text files.

while parsing `wiki-text` is particularly over-complicated (the cost of any markup syntax), choosing not to simply retrieve HTML from MediaWiki's APIs give us more freedom to build any other project we want to.

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


then run `python app/server.py` and make a change to a wiki article using MW web interface: a message should appear on the terminal, detecting which page has been modified.

## mediawiki

a local instance of mediawiki must be run, in order to have this software working correctly.

check this repo to set up a MW instance: <https://github.com/hackersanddesigners/hd-mw>

## Local dev setup and TLS certificates

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

#### settings.toml

this file mainly set website preferences, eg general wiki options:

- `wiki.frontpage`: which wiki article to we want to use for the website frontpage?
- `wiki.categories.<cat>`: sets a list of categories to define which wiki articles we want to display on the website. the `<cat>` is the actual MediaWiki category we want to use. then, each category has some more options:
  - `parse`: should we parse it (eg download every article of that category) or not; useful when working on the codebase to speed up parsing process if using `python cli.py build-wiki`, for instance
  - `nav`: should the category be displayed in the navigation
  - `fallback`: using this category as fallback, in case the wiki article has no matching category with the given list of categories
  - `label`: some categories in the wiki might be called something, and we might want to display them in a different way in the navigation, in the URL path, etc

and specific plugin options:

- `tool-plugin.host_default`: which git hosting service fallback is the H&D MW Tool plugin using?
- `tool-plugin.host_default`: a dictionary of git hosting services the H&D MW Tool wants to use
- `tool-plugin.branch_default`: a list of branches to use when parsing information from the git repo set in the plugin; this works as a progressive list of fallback branch names

## commands

there is a CLI program at `cli.py` to run common operations. currently available commands are:

- `setup`: creates a bunch of necessary folders to run the website
- `server`: starts a local server and listen to specified port at UDP messages from the MediaWiki instance; whenever a new message comes in, it runs the `app/build_article.py` functions to parse and save a new version of the received article to disk

- `build-wiki`: rebuilds the entire wiki, where by entire it's meant the list of articles with specific categories defined in `settings.toml`; it runs `app/build-article.py` to do so

- `make-article`: helper function to trigger a change in the MediaWiki instance, instead of manually loggin in to the MW editor and commit a change. the command takes two arguments: `PageTitle` and type of operation (`edit`, `delete`); the `edit` operation creates a new article if it does not exist yet.

start off by running `python cli.py --help` to see the available options.

to run a local web-server in order to browse the `wiki` folder, you can do:

- `uvicorn app.main:app --reload` or use `local-server.sh`.


## sort index page notes

<2023-09-27> we removed the sorting option as for performance reasons we do the sorting only on the
paginated subset of articles (because we need to parse each article to retrieve the date field, etc).

given it's not particularly useful in retrospect we keep the code but disable it. to put it back:

- re-enable function in `app/main.py`
- add back to each desired template link / button, the following Jinja2 filter:
  ```
  <a href="{{ request.url | query_check('sort_dir', 'type') }}">{{ page }}</a>
  ```
- lookup `/app/views/template_utils.py/query_check` for more info

this feature was 90% done, so if you enable it again, please double-check if anything is missing.

## self-help

known problems so far:

- keep one category per article, else the parser might pick up any other category option added to the list of categories. this is due to the fact that we're reading from a dictionary of categories and by default Python does not keep the dictionary "ordered". ad of <2023-10-11> we agreed to keep one category per article, if that will change in the future, the problem will be bigger — as we organize articles in the wiki by directories (one directory is one category), having multiple category will produce duplicate articles across several directories.


## License

This repository is published under the [CC4r*](LICENSE) license.
