import json


def main(data):
    """
    pretty-print json data
    """

    print("data =>", json.dumps(data, indent=4))
