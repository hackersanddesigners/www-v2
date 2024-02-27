import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main():
    """
    copy assets folder from root directory to ./wiki/.
    """

    ASSETS_DIR = os.getenv('ASSETS_DIR')
    WIKI_DIR = os.getenv('WIKI_DIR')
    input_path = Path(ASSETS_DIR).resolve()
    dest_path = Path(WIKI_DIR).resolve() / 'assets'

    shutil.copytree(input_path, dest_path, dirs_exist_ok=True)





    
