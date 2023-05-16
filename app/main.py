from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


app = FastAPI()

base_dir = Path.cwd()

app.mount("/",
          StaticFiles(directory=base_dir / "wiki", html=True),
          name="wiki")
app.mount("/assets/media",
          StaticFiles(directory=base_dir / "wiki/assets/media"),
          name="media")

# TODO this route is not working ):
# we're instead copying CSS and JS files into wiki/assets
# when running build-wiki for instance
# maybe it's due to setting `/` with html=True
# making that path the root path?
app.mount("/static",
          StaticFiles(directory=base_dir / "static"),
          name="static")
