import sys
from pathlib import Path

import tomli


def main():
    """
    Read settings.toml from the root of the project folder
    """

    try:
        filepath = Path.cwd().absolute() / "settings.toml"
        with open(filepath, mode="rb") as f:
            config = tomli.load(f)
            return config

    except FileNotFoundError:
        print(
            f"error => {filepath} has not been found\n",
            "        please check the README for instructions",
        )
        sys.exit(1)
