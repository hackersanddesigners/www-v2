from os import getenv
from pathlib import Path


def file_lookup(filename: str) -> list[str]:
    """
    Recursively check if given filename is found
    in WIKI_DIR and return list of results.
    """

    WIKI_DIR = Path(getenv('WIKI_DIR'))
    
    pattern = f"**/{filename}.html"
    paths = [p for p
             in WIKI_DIR.glob(pattern)]

    return paths
