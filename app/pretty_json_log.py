from typing import Any
import json


def main(data: dict[str, Any]) -> None:
    """
    Helper function to pretty-print json data.
    """

    print("data =>", json.dumps(data, indent=4))
