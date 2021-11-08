# hackersanddesigners.nl v2


  - static + search
  - 

- a static site generator that creates a new page whenever a change is done on the wiki (using [wgRCFeeds](wgRCFeedshttps://www.mediawiki.org/wiki/Manual:%24wgRCFeeds) UDP messaging)
- a Flask app providing a search interface to display results from the wiki, and other sources

structure:

  - `<h&d.nl>` (frontpage as `static-page.html`)
  - `<h&d.nl/p/static-page.html>`
  - `<h&d.nl/s/<search-query>`
  
  
MediaWiki's `LocalSettings.php`, `RCFeeds` example:

```
$wgRCFeeds['had-py'] = array(
    'formatter' => 'JSONRCFeedFormatter',
    'uri' => 'udp://localhost:1338',
    'add_interwiki_prefix' => false,
    'omit_bots' => true,
);
```

