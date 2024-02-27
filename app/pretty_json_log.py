import json


def main(data):
    """
    Helper function to pretty-print json data.
    """

    print("data =>", json.dumps(data, indent=4))
