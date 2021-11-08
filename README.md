# hackersanddesigners.nl v2

# intro

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
