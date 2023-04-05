from aiofiles  import os
from slugify import slugify


async def delete_article(page_title: str):
    """
    remove local wiki article if it exists
    """

    fn = f"wiki/{slugify(page_title)}.html"

    if await os.path.exists(fn):
        await os.remove(fn)
        print(f"delete-article: {page_title} removed")

    else:
        print(f"delete-article: {page_title} not found, nothing done")
