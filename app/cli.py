from dotenv import load_dotenv
import os
import typer
from typing_extensions import Annotated
import asyncio
import time
from build_wiki import main as bw
load_dotenv()


app = typer.Typer()

@app.command()
def build_wiki(
        index_only: Annotated[bool, typer.Option(help="build only Index pages")] = False,
):

    ENV = os.getenv('ENV')
    URL = os.getenv('BASE_URL')

    start_time = time.time()
    # -- run everything
    asyncio.run(bw(ENV, URL, index_only))
    print("--- %s seconds ---" % (time.time() - start_time))


@app.command()
def build_article():
    print(f"build article")


if __name__ == "__main__":
    app()
