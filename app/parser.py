import os
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
from dotenv import load_dotenv
from slugify import slugify

from app.file_ops import file_lookup
from app.read_settings import main as read_settings

load_dotenv()


config = read_settings()
MEDIA_DIR = os.getenv("MEDIA_DIR")


def link_rewrite_to_canonical_url(link):
    """
    Given a URL like:
    https://hackersanddesigners.nl (no subdomain

    Rewrite it to be in relative format, eg.
    pointing to a page in *this* wiki.
    """

    url_parse = urlparse(link.attrs["href"])
    uri = slugify(url_parse.path.split("/")[-1])
    matches = file_lookup(uri)

    if len(matches) > 0:
        filename = str(matches[0]).split(".")[0]
        new_url = "/".join(filename.split("/")[1:])
        link.attrs["href"] = f"/{new_url}"
    else:
        link.attrs["href"] = uri


def link_image_update(link, img_tag, mw_url):
    """
    Update any img's srcset attribute to the correct URL format.
    """

    img_tag.attrs["src"] = f"{mw_url}{img_tag.attrs['src']}"

    if "srcset" in img_tag.attrs:
        srcset_list = [url.strip() for url in img_tag.attrs["srcset"].split(",")]

        srcset_list_new = []
        for item in srcset_list:
            tokens = item.split(" ")
            tokens[0] = f"{mw_url}{tokens[0]}"
            srcset_new = " ".join(tokens)

            srcset_list_new.append(srcset_new)

        if srcset_list_new:
            img_tag.attrs["srcset"] = ", ".join(srcset_list_new)


def link_extract_image_URL(links, mw_url):
    """
    Extract image's URL from a list of links.
    Update URL to point to specified MediaWiki instance.
    """

    def extract_image_URL(img):
        img_name = None
        src = img.attrs["src"]

        # fetch File:<name> by the parent tag, eg. the <a>.
        # doing it through the img's src URL contains sometimes
        # a thumb filename prefix in it, eg `520px-<image-name>.jpg`
        # which breaks our code when using MW's thumb APIs below.
        if "href" in img.parent.attrs:
            img_name = img.parent.attrs["href"].split("File:")[-1]
        else:
            img_name = src.split("/")[-1]

        # af <2024-02-12>
        # we can't just set an arbitrary thumb width value as below,
        # since sometimes original images are smaller (in width) of
        # the set thumb width value. this silenty fails and returns
        # no valid image URL, therefore displaying the img alt text
        # in the frontend.

        # therefore one way (1) to go about this is to parse the rest
        # of the HTML img tag and extract if possible the set width
        # value in it, either via the `width` attribute, or by parsing
        # the srcset attribute and read from the first URL the given
        # width value (slightly more complicated).

        img_width = None

        if "width" in img.attrs:
            img_width = int(img.attrs["width"])

        elif "srcset" in img.attrs:
            srcset = img.attrs["srcset"]

            # <http://localhost/images/thumb/b/b4/Mediachoreo5.jpg/240px-Mediachoreo5.jpg 1x,
            #  http://localhost:8001/images/thumb/b/b4/Mediachoreo5.jpg/480px-Mediachoreo5.jpg 2x>
            # - we split the srcset list by `,`
            # - then by ` ` between the URL and the <n>x signature to get the URL only,
            # - then by `/` and get the last part of it
            # - then by `px` to get the width of the image
            # - and convert the width to integer

            srcset_big = srcset.split(",")[-1].strip()

            width_x = srcset_big.split(" ")[0]
            width_x = width_x.split("/")[-1]
            width_x = width_x.split("px")[0]

            if width_x.isdigit():
                img_width = int(width_x)

        thumb = src
        thumb_width = 250

        # if img_width is equal or bigger than thumb_width value
        # make thumb version of given img, else use the original
        # src URL.

        # TODO @karl: the MW thumb API works very inconsistently. i figured
        # that some of the missing images in the index page are due to passing
        # a "wrong" thumb_width value to the URL. while fiddling with it, i
        # discovered specific images "wants" specific thumb_width values.
        # i believe we either have the thumb API setup incorrectly, or the
        # API is broken.
        if img_width is not None and img_width >= thumb_width:
            thumb = f"{mw_url}/thumb.php?f={img_name}&w={thumb_width}"

        alt = img.attrs["alt"]

        img_data = {"src": src, "thumb": thumb, "alt": alt}
        imageURLs.append(img_data)

    imageURLs = []

    for link in links:
        if link.img:
            img = link.img
            extract_image_URL(img)

            # strip images of their wrappers
            # we do this at the end because we
            # parse the <a> wrapping the <img>
            # to retrieve the image URL
            link.parent.attrs["class"] = "image"
            link.unwrap()

    return imageURLs


def link_rewrite_image_url(link, mw_url):
    """
    Update URL for link pointing to an image file.
    """

    if "=File:" in link.attrs["href"]:
        # update <img> wrapping <a> href
        link.attrs["href"] = f"{mw_url}{link.attrs['href']}"

        # update <img> tag
        if link.img:
            img_tag = link.img

            link_image_update(link, img_tag, mw_url)
            # strip_thumb(img_tag)


def link_rewrite_other_url(link):
    """
    Update URL for any other link that is not pointing
    to a `File:`.
    """

    # TODO
    # this file-lookup is done to make sure
    # articles' filename on disks matches
    # URL used in the article files.
    # as of <2023-11-08> i am not entirely sure
    # this is useful, but when thinking about it
    # it could be well helpful.

    if "=File:" not in link.attrs["href"]:

        url_parse = urlparse(link.attrs["href"])
        uri_title = unquote(url_parse.query.split("=")[-1])
        uri = slugify(uri_title)
        matches = file_lookup(uri)

        if len(matches) > 0:
            filename = str(matches[0]).split(".")[0]
            new_url = "/".join(filename.split("/")[1:])
            link.attrs["href"] = f"/{new_url}"
        else:
            link.attrs["href"] = f"/{uri}"


def strip_thumb(thumb):
    """
    Strip "thumb" image from its hardcoded width and height attributes.
    """

    if "src" in thumb.attrs:
        # strip height and width from image attribute
        for attr in ["height", "width"]:
            if attr in thumb.attrs:
                del thumb.attrs[attr]


def post_process(
    article: str,
    file_URLs: [str],
    HTML_MEDIA_DIR: str,
    redirect_target: str | None = None,
):
    """
    Update article HTML before saving it to disk:
    - update links
    - extract list of images URLs
    - manipulate and clean-up HTML for better design
    - extract repo URL from <tool> HTML
    """

    canonical_url = config["domain"]["canonical_url"]
    mw_url = config["domain"]["mw_url"]

    soup = BeautifulSoup(article, "lxml")

    # -- update URLs for File: and any other URL type
    links = soup.find_all("a")
    for link in links:
        if "title" in link.attrs:
            link.attrs["title"] = link.text

        if link.has_attr("href"):
            if link.attrs["href"].startswith(canonical_url):
                link_rewrite_to_canonical_url(link)

            elif link.attrs["href"].startswith("/index.php"):
                link_rewrite_image_url(link, mw_url)
                link_rewrite_other_url(link)

    # -- extract a list of image URLs for the article
    imageURLs = link_extract_image_URL(links, mw_url)

    # add a tag class for iframe wrappers
    iframes = soup.find_all("iframe")
    for iframe in iframes:
        iframe.parent.attrs["class"] = "iframe"

    # -- tool parser
    tool_repos = soup.find_all("a", class_="inGitHub")
    repos_index = []
    for repo in tool_repos:
        href = repo.attrs["href"]
        repos_index.append(
            {
                "href": href,
                "name": href.split("/")[-1],
                "user": href.split("/")[-2],
                "host": href.split("/")[-3],
            }
        )

    # -- return article HTML
    # the wiki article can be empty
    # therefore soup.contents is an empty list
    if len(soup.contents) > 0:
        t = "".join(str(item) for item in soup.body.contents)
        article = t

    return article, imageURLs, repos_index


def get_table_data_row(td):
    """
    Extracts data from HTML's <td> tag
    """
    # somewhere here, when the PeopleOrganization field is a
    # list, it only parses the first name and not all

    for item in td.children:
        if isinstance(item, NavigableString):
            continue
        if isinstance(item, Tag):

            # <td> contains the data in the format
            # => {key}::{value}, let's get only the value
            content = item.string.split("::")[-1]

            return content


def get_data_from_HTML_table(article_html):
    """
    Extracts data from HTML's <tbody> tag: we map over
    each <th> element and check if it matches against any
    of the specified keys in table_keys. Those keys are taken
    from MW's own table keys and it's the subset of data we
    care about.
    """

    table_keys = ["Name", "Location", "Date", "Time", "PeopleOrganisations", "Type"]

    soup = BeautifulSoup(article_html, "lxml")
    table = soup.find("tbody")

    # <tr> => table-row
    # <th> => table-header (where we check for a given key)
    # <td> => table-datacell (where we fetch our desired content)

    info = {}

    if table is not None:
        for tr in table.children:
            # we skip DOM strings and look only for DOM tags
            if isinstance(tr, NavigableString):
                continue
            if isinstance(tr, Tag):
                table_key = tr.th
                if table_key is not None and table_key.string is not None:
                    table_key = table_key.string.strip()

                    if table_key in table_keys:
                        if tr.td:
                            info[table_key.lower()] = None
                            info[table_key.lower()] = get_table_data_row(tr.td)

        table.decompose()

    return info


def get_metadata(article):
    """
    Extract wiki template tags from article, if any.
    Extract article's categories too.
    """

    metadata = {
        "info": {},
        "categories": [],
    }

    info = get_data_from_HTML_table(article["text"])
    metadata["info"] = info

    cats = config["wiki"]["categories"]

    categories = get_categories(article["categories"], cats)
    metadata["categories"] = [slugify(cat) for cat in categories]

    return metadata


def get_categories(categories, cats) -> [str]:
    """
    Extract article's categories and handle
    eventual fallback situations.
    """

    cat_fallback = None

    for k, v in cats.items():
        if v["fallback"]:

            cat_fallback = v

    cat_fallback_label = cat_fallback["label"]

    if len(categories) > 0:
        # (1) we manually remove the cat Article from each article
        # as it is added by default when using the template: Article
        # in MW.
        # (2) we make sure that every cat is part of the list of
        # set categories in settings.toml

        return [
            cat["category"]
            for cat in categories
            if not cat["category"] == "Article" and cat["category"] in list(cats.keys())
        ]

    else:
        return [cat_fallback_label]


def parser(article: dict[str, int], redirect_target: str | None = None):
    """
    Parse given article dictionary by:
    - extracting metadata (images, categories, templates, tables, etc.)
    - post-process HTML (fix links, extract Tool metadata, etc.)
    """

    print(f"parsing article {article['title']}")

    HTML_MEDIA_DIR = "/".join(MEDIA_DIR.split("/")[1:])

    metadata = get_metadata(article)

    body_html, imageURLs, repos_index = post_process(
        article["text"], article["images"], HTML_MEDIA_DIR, redirect_target
    )

    metadata["repos_index"] = repos_index

    print(f"parsed {article['title']}!")

    return body_html, metadata, imageURLs
