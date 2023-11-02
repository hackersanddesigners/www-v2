# notes

## name

previous name: `had-py`
new name: 

  - static + search
  - ??

## structure

| area           | current routing                     | new routing               |
|----------------|-------------------------------------|---------------------------|
| root           | `/`                                 | `/`                       |
| file           | `/<file>`                           | `/files/<file>`           |
| page           | `/p/<page>` and `/title=<page>` (?) | `/<page>`                 |
| section        | `/s/<section>`                      | `/<section>`              |
| section's page | `/s/<section>/p/<page>`             | `/<section>/<page>`       |
| search         | none                                | `/search?q=<search+term>` |

basic idea: remove the REST-like elements like `/s/` or `/p/` from the URL. setup an Nginx rule to catch any URL using that format and rewrite it to the new format.

another option would be to keep the same URL structure, but at least rewriting all incoming URLs to lowercase?

to figure out:

- how many nesting levels do we have?
- do we want to still rely on `<section>` as index page?
- do we need to adjust / re-organize the wiki side as well or do we avoid to map the two (wiki and this frontend website) 1:1?

the the levels of navigation is build using the Semantic Media Wiki *Concept* option: grouping together pages matching a specific query (with multiple elements).

| area                  | type    | query                                          |
|-----------------------|---------|------------------------------------------------|
| main nav              | concept | `[[Category:Article]] [[MainNavigation::Yes]]` |
| activities            | concept | `[[Category:Event]] [[Type::Meetup]]`          |
| collaborators         | concept | `[[Category:Collaborators]]`                   |
| publishing            | concept | `[[Category:Publishing]]`                      |
| tools                 | concept | `[[Category:Tools]]`                           |
| summer academy <year> | concept | `[[Category:Event]] [[Type::HDSA2022]]`        |

generally speaking, we're using Semantic Media Wiki *only* for this feature, primarily due to the limitations (at least at the time six years ago coupled with my inexperience) of the MediaWiki APIs. eg, can we do the same API queries listed above through the normal API operations? in that way we would avoid a fairly complicated to maintain extension (Semantic Media Wiki) and the code would be maybe a little simpler to follow.

- `nav`: combine main nav and sub nav, or place sub nav on the left / right side, or make it accessible in some other way
- `home`: no reason to show event archive in its entirety, or at all?
- `section` pages:
  - allow to sort and filter
  - make list view to display more info, instead of grid image-based view?
- `activities`: 
  - setup public event calendar that one can subscribe to?
  - allow to add event to one's calendar program (ics)
- `tools/<page>`: make wiki template with specific fields (repo URL, authors, license, etc)
- `summer-academy`: ask juju if anything is missing or needed

### update <2023-04-19>

after 6 months in, we're at a good stage of fetching data and shape it how we like. atm currently working out the website structure, and thinking most items in the current primary and secondary navigation are there due *also* to not making index pages more "interactive". 

for instance: while we can still have fast links (in the nav) to each summer academy, we can also display those pages by going to the Events page, sort + filter by Event's type (eg, by `HDSA2022`) and get similar results. clearly making ad-hoc pages for each summer academy edition is a "faster" way to browse through the website than asking the end-user to do that themselves, still it makes the website a bit too predefined?

## process

at last a decent understanding of how to use the powerful `wikitexthtml` package to handle the process of converting a MediaWiki article into an HTML document:

- we receive a message from the wiki server that an article has been updated
- we feed the title of the wiki document into `wikitexthtml` and get an instance of the document as a Page object:
  - `wikitexthtml` allows itself to be modified and adjusted based on one's needs by extendig it as a class, and customizing its methods (eg check if the article exists and load it, check if a file exists and fetch it, etc) at will:
  - we tailor this approach to our workflow of:
    - check which type of update has happened by reading the wiki server message update (article creation, modification, deletion)
    - accordingly create, update or delete a new, or possibly existing, HTML document, and use different degrees of caching (eg check if the files attached with a certain wiki article have changed, if not, do not re-fetch them from the wiki server, etc) in relation to it
    - do pre- and post- processing operations to fix eventual data input malformation (from the wiki article syntax)
    - we do all this by using our tailored-fit class methods accessible from the Page object we created
    
this helps to compact the existing WIP functions to work with the wiki article input data inside one class and keep things and the core workflow organized.
    
in terms of document "lifecycle", we want to:

- fetch a newer version of a given wiki article, or delete it from out local HTML database; checking if the article exists does not help much in our case, as we receive a message update from the wiki server about a change happened to an existing, or just deleted, wiki article — so propably keeping the method `page_exists` seems unnecessary => actuallt used internall by wikitexthtml so it's necessary for its functioning
- check if any file attached to a given wiki article has been changed, as well as checking if compared to our local db version, any file has been deleted in the update
  - this could have at least two approaches:
    - trust blindly the wiki article and re-fetch every file from it
    - check if an existing copy of the file is already present in our local db, check if it has changed, if yes fetch a newer copy of it
  - but: how do you keep track of files that have been deleted from an article? i haven't checked this out yet, but the wiki message update could be able to give us this info; if not, we can anyway see if a file is still part of an article and if not (by cross checking the files we have locally) we could remove it
    - this means though we keep files inside the same subfolder where the article lives?
    - else how do you keep track of it by cross-checking?
    - better would be to implement a method that checks which files have been removed from a given article, then check if those files are used anywhere else in the wiki (by doing a lookup to that specific file) and based on that info remove a given file from a shared folder with all the files used in the wiki
    - this also brough up a question: we want to build a full archival system, therefore making local copies of files is necessary, yet if we run the main version of this frontend website of the wiki on the same server where we have the MediaWiki instance, we are duplicating a lots of data — not only images and videos, but also text information; this is not happening with the current version of the frontend which uses an REST API-based approach to retrieve data...
    - we could either pass a flag / option and write more code to handle two use-cases (symlink-like / points resources to local MediaWiki instance, and full-archival approach), or stick with the full archival approach and duplicate all that data
    - thing is: to keep the setup simple, we need to have a local server that listens to the UDP message being sent by the wiki server in any case /:
    
## limitations

### index page article sorting

currently, as of <2023-08-22>, index pages sort their content in a limited way: they can only sort the list of item visibile on the current page, instead of sorting the whole list of items across pages. this is becausue we use pagination to fetch data from the APIs. how so?

MediaWiki's API have lots of strange limitations or weird way to work. in our use case, to retrieve a list of all the event articles, we need to perform a two-step operation:

1. we fetch a list of "category member" articles, which contains a `page id`, `ns` (namespace) and `title`. while we can ask to get back more fields than these, we cannot get back the fields we would like to use to sort out our list of event articles.
2. afterwards, we loop over the above list and fetch each article in its entirety, squeezing everything we can out of it to get all the data possible. in this step we get the fields we are interested in (in the case of the Events page, beside `title` these are: `location`, `date`, `time`, `type`), but to do so we have to *extract* them from the article's content / body field. these fields are inside a table data structure, part of the wikitext syntax, and therefore cannot be parsed from the category member APIs — since at that step we only work with articles ids mostly.

given this situation, parsing a list of 300 articles in its entirety, takes arond 5 seconds or more (since we must perform the two steps above). to be able to still make use of the MediaWiki APIs, we implement a pagination function before parsing each article. that is: we fetch the list of all articles of a certain category, then we split the list in smaller lists of articles which we fetch and parse. this helps to keep the loading time of the webpage to a decent amount. the downside though, is that since we're paginating our results in order to keep the required time low, we are "forced" to do the same also when sorting our list of article. which means: we sort the paginated sub-list of articles at a time.

#### possible remedies

as part of the archive feature of the website (the main reason to build this piece of software in the first place), we are going to store each wiki article in its wikitext "plain syntax" on disk. eg, we are writing each article on disk as a text file. if we do this, we could leverage the fact of having a cache of all the wiki articles, and do our sorting computation in one go — since we don't need to first get back a list of all the IDs of a certain category, and then fetch each article, but rather can parse, filter, and sort in one go.

alternatively, or as an addendum, we could really setup a hot-cache (?) layer using `sqlite`. infrastracturally, it's just a binary file, so there's low maintenance unlike other SQL databases, but in terms of performance and utility it would really shine, as: 

- only the website would the writing to it (eg acting as the only user accessing sqlite)
- we would be using it for read-only operations, and if we setup some tables we would be able to retrieve, filter, sort, etc across all wiki articles much easier and faster than using MediaWiki's APIs.

clearly setting up the sqlite takes some time, but probably less headaches and  maintenance than figuring out how to do something with MediaWiki. having a two-layers cache (text files and sqlite) would also help in case something changes in the article or webiste structure, and we need to rebuild the sqlite tables from scratches, as we can use the text file archive as data source.

## archive

originally the whole software was born out of a desire to keep a wikitext "plain-text" cache of the MediaWiki, as a way to make backup easier to maintain. today <2023-11-02>, while starting to actually work on it, i wondered if this is a good idea still?

work-wise, it only takes one more function to write the wikitext as file on disk, plus some git-helper functions if we want to host it in a git repo.

in terms of benefits from using it though, what would we gain:

- we need to parse once again the wikitext into some useful format and convert it into another format. do we use the [wikitextparser](https://github.com/5j9/wikitextparser) (or equivalent) like we're doing now, and then do something with it?
- wouldn't HTML overall be a little more structured, and so a little be easier to parse with the myriad of existing tools — unlike the very loosy wikitext syntax?
  - the downside is that if we rely on the HTML files used to build the website, we would have extra HTML used for general website layout, and possibly some filtering work done already at the level of the wikitext syntax to fit the needs of the website
  
overall i can't tell if this archive is ever going to be used much as an input for other projects, and probably relying on the static HTML folder could be enough. if more needs arise, it takes one more function to save the wikitext version of each article into a file, or redirect it to some other specific function / project.
