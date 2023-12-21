from dotenv import load_dotenv
import os
import typer
from typing_extensions import Annotated
import asyncio
import time
from app.server import main as srv
from app.build_wiki import main as bw
from app.make_change_in_wiki import main as mc
load_dotenv()


app = typer.Typer()


@app.command()
def setup():
    """
    Setup necessary folders and files to run the program.
    """

    WIKI_DIR = os.getenv('WIKI_DIR')
    MEDIA_DIR = os.getenv('MEDIA_DIR')
    LOG_DIR = os.getenv('LOG_DIR')

    dir_list = [WIKI_DIR, MEDIA_DIR, LOG_DIR]

    for path_dir in dir_list:
        dir_path = os.path.abspath(path_dir)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"created {dir_path}")
        else:
            print(f"{dir_path} exists already")


@app.command()
def server():
    """
    Run server to receive a message whenever an article from the MediaWiki is updated
    (add, edit, rename, delete).
    Create an HTML version of the article.
    """

    SERVER_IP = os.getenv('SERVER_IP')
    SERVER_PORT = int(os.getenv('SERVER_PORT'))
    ENV = os.getenv('ENV')

    asyncio.run(srv(SERVER_IP, SERVER_PORT, ENV))
    

@app.command()
def build_wiki():
    """
    Rebuild entire wiki from scratch.
    """

    URL = os.getenv('BASE_URL')
    ENV = os.getenv('ENV')

    start_time = time.time()
    # -- run everything
    asyncio.run(bw(ENV, URL))
    print("--- %s seconds ---" % (time.time() - start_time))


@app.command()
def make_article(article: Annotated[str, typer.Argument(help="article to work with")],
                 operation: Annotated[str, typer.Argument(help="operation type: edit, delete")]):
    
    """
    Update or delete an article in the MediaWiki
    and create a new HTML version of it.
    """
    
    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')

    asyncio.run(mc(ENV, URL, article, operation))


if __name__ == "__main__":
    app()
