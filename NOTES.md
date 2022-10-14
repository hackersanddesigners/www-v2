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

