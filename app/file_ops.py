import asyncio
import os
import subprocess
import sys
from pathlib import Path

import aiofiles
from dotenv import load_dotenv

load_dotenv()


WIKI_DIR = os.getenv("WIKI_DIR")


def file_lookup(filename: str) -> list[Path]:
    """
    Recursively check if given filename is found
    in WIKI_DIR and return list of results.
    """

    # TODO look how to make this pattern work
    # so we can match also partial URI
    # pattern = f"*{filename}*.html"

    pattern = f"{filename}.html"
    paths = [p for p in Path(WIKI_DIR).glob(pattern)]

    return paths


def search_file_content(pattern: str) -> list[str]:
    """
    Run a ripgrep search with the given pattern
    inside WIKI_DIR and return a list of filepaths.
    """

    try:
        RG_PATH = subprocess.check_output(
            ["/usr/bin/which", "rg"], text=True, cwd=WIKI_DIR
        ).strip()

    except subprocess.CalledProcessError:
        # no ripgrep (rg) found in the system.
        # stop everything and exit. print a user-facing
        # message asking to install ripgrep.
        print(
            "search_file_content error =>  ripgrep is not installed\n",
            "in the system. please install it, see README.md",
        )
        sys.exit(1)

    print(f"RG_PATH => {RG_PATH}")

    try:
        # we're `cd`-ing into WIKI_DIR by passing the option
        # `cwd=WIKI_DIR, so we don't pass to `rg` a base-dir path
        # at it's assumed to default to CWD
        matches = subprocess.check_output(
            [RG_PATH, "--type", "html", "--files-with-matches", pattern],
            text=True,
            cwd=WIKI_DIR,
        )

        results = matches.splitlines()
        return results
    except subprocess.CalledProcessError:
        # no rg match. return empty list.
        print(f"search-file-content => no match for {pattern}")

        return []


async def write_to_disk(
    page_slug: str | None,
    document: str,
    sem: asyncio.Semaphore | None = None,
    is_styles_page: bool = False,
):
    """
    Write given file to disk. We wrap the actual function in an
    extra function that checks whether the sem parameter is used,
    so as to iterate with it accordingly.
    """

    async def write(page_slug: str | None, document: str):
        if page_slug is not None:
            file_path = f"./{WIKI_DIR}/{page_slug}.html"
            if is_styles_page:
                file_path = f"./{WIKI_DIR}/assets/styles/{page_slug}.css"
            async with aiofiles.open(file_path, mode="w") as f:
                try:
                    await f.write(document)
                    print(f"✓ {page_slug} has been correctly written to disk")
                except Exception as e:
                    print(f"✕ error for {page_slug} => {e}")

    if sem is not None:
        async with sem:
            await write(page_slug, document)

    else:
        await write(page_slug, document)
