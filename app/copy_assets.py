import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    """
    Copy assets folder from root directory to WIKI_DIR.
    """

    ASSETS_DIR = os.getenv("ASSETS_DIR")
    WIKI_DIR = os.getenv("WIKI_DIR")
    input_path = Path(ASSETS_DIR).resolve()
    dest_path = Path(WIKI_DIR).resolve() / ASSETS_DIR
    print(f"copied static assets to {dest_path}")

    shutil.copytree(input_path, dest_path, dirs_exist_ok=True)
