from dotenv import load_dotenv
import os
import typer
from typing_extensions import Annotated
import asyncio
import time
from app.server import main as srv
from app.build_wiki import main as bw
from app.make_change_in_wiki import main as mc
from app.main import main as mws
import asyncio
load_dotenv()


app = typer.Typer()


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
def build_wiki(index_only: Annotated[bool, typer.Option(help="build only Index pages")] = False):
    """
    Rebuild entire wiki from scratch.
    Pass --index-only to re-create only index pages (faster).
    """

    URL = os.getenv('BASE_URL')
    ENV = os.getenv('ENV')

    start_time = time.time()
    # -- run everything
    asyncio.run(bw(ENV, URL, index_only))
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


@app.command()
def local_server():
    """
    Run local web-server to browse wiki HTML folder.
    """
    
    asyncio.run(mws())


if __name__ == "__main__":
    app()
