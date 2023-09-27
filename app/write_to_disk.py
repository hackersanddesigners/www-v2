from pathlib import Path
import aiofiles

async def write(page_slug: str, document: str, ext):
    """
    write file to disk; make necessary directories if part of the path.
    """

    # let's check if page_slug contains a parent dir (or more) as part of it
    # if going up one level (parent) and expanding the path (expanduser)
    # return `.`, there's no dir in the path
    cat_dir = f"./wiki/{Path(page_slug).parent.expanduser()}"
    if cat_dir != '.':
        t = await aiofiles.os.makedirs(cat_dir, exist_ok=True)

    async with aiofiles.open(f"./wiki/{page_slug}.{ext}", mode='w') as f:
        try:
            await f.write(document)
            print(f"✓ {page_slug} has been correctly written to disk")
        except Exception as e:
            print(f"✕ error for {page_slug} => {e}")


async def main(page_slug: str, document: str, sem, ext='html'):
    if sem is not None:
        async with sem:
            await write(page_slug, document, ext)

    else:
        await write(page_slug, document, ext)
