from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


app = FastAPI()

base_dir = Path(__file__).parent.parent
app.mount("/", StaticFiles(directory=base_dir / "wiki", html=True), name="wiki")
app.mount("/static", StaticFiles(directory=base_dir / "static"), name="static")
