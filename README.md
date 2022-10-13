# hackersanddesigners.nl v2

## setup

we are using Python 3.8 at the time of writing and handle managing Python's packages and virtual environments with [pipenv](https://pipenv.pypa.io/en/latest/). `pipenv` is not necessary, as you can use Python's `virtualenv` to set up a working environment with a specified Python version, as well as using `pip` to install the necessary packages. 

following are reported both options.

### virtual environment

if you are willing to use `pipenv`, then do:

```
pipenv shell
```

and the first time it should setup a new virtual environment for your user.

else you can:

- make virtual environment: `python3 -m venv env`
- activate virtual environment: `source env/bin/activate`
- do `pip freeze > requirements.txt` after installing a new package to update list of packages

### packages

if using `pipenv`, do:

```
pipenv install
```

else to install all packages do: 
- make sure to upgrade pip: `python3 -m pip install --upgrade pip`
- then try: `python3 -m pip install -r requirements.txt`

## intro

a program to export data from MediaWiki into a mostly static website (except `/search`).

the underlying idea is to make it easier to archive and distribute the website in an easier format to work with: 

- we export each article into its Mediawiki plain text syntax
- add it to a git repo
- distribute the repo across computers

we also save to HTML the article content so to have less breaking states of the website, and distribute that into the git repo too. we include images and other files part of each article.

backing up the Mediawiki's SQL db that we run our website off is part of the plan too, but the whole MW system feels too complex and obscure to be worth it spending so much time on it.

once we have all the wiki data articles out we can do, anything!

## details

- a static site generator that creates a new page whenever a change is done on the wiki (using [wgRCFeeds](wgRCFeedshttps://www.mediawiki.org/wiki/Manual:%24wgRCFeeds) UDP messaging)
- a Flask app providing a search interface to display results from the wiki, and other sources

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


then run `python server.py` and make a change to a wiki article using MW web interface: a message should appear on the terminal, detecting which page has been modified.

## mediawiki

a local instance of mediawiki must be run, in order to have this software working correctly. 

we need to export:

- SQL database
- images folder
- LocalSettings.php
- XML dump

to export a copy of an existing (possibly online) database, do:

```
mysqldump -h hostname -u userid -p --default-character-set=whatever dbname > backup.sql
```

> Substituting hostname, userid, whatever, and dbname as appropriate. All four may be found in your LocalSettings.php (LSP) file. hostname may be found under $wgDBserver; by default it is localhost. userid may be found under $wgDBuser, whatever may be found under $wgDBTableOptions, where it is listed after DEFAULT CHARSET=.

see this article for more details: <https://www.mediawiki.org/wiki/Manual:Backing_up_a_wiki#Mysqldump_from_the_command_line>

for the images folder and LocalSettings.php, make a backup from the Mediawiki instance running online.

to export a dump of the XML data, do:

```
cd /path/to/mediawiki/ && cd maintenance

php dumpBackup.php --full --quiet > dump.xml
```

then we need to restore all this data: <https://www.mediawiki.org/wiki/Manual:Restoring_a_wiki_from_backup>.

- re-create database
- import database
- import XML dump
- copy images folder
- copy LocalSettings.php

see also the MediaWiki installation guide to setup an initial wiki from scratch: <https://www.mediawiki.org/wiki/Manual:Installing_MediaWiki>. the MediaWiki instance can be installed next to this repo, or in any case elsewhere on the system. we need to communicate between the servers of both websites.
