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
