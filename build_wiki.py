from dotenv import load_dotenv
import os
import tomli
from requests import Session
from requests_helper import main as requests_helper
from requests_helper import query_continue
load_dotenv()


ENV = os.getenv('ENV')
URL = os.getenv('BASE_URL')


def main():
    """
    this function (re-)build the entire wiki by fetching a set of specific
    pages from the MediaWiki instance
    """

    def get_category(cat: str):
        req_op = {
            'verb': 'GET',
            'url': URL,
            'params': {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': f"Category:{cat}",
                'cmlimit': '50',
                'cmprop': 'ids|title|timestamp',
                # 'cmsort': 'timestamp',
                # 'cmdir': 'asc',
                'formatversion': '2',
                'format': 'json',
                'redirects': '1',
            },
            'session': False,
            'stream': False
           }

        data = []
        for response in query_continue(req_op, ENV):
            x = response['categorymembers']
            if len(x) > 0 and 'missing' in x[0]:
                title = x[0]['title']
                print(f"the page could not be found => {title}")
                return False

            else:
                data.extend(x)

        return data

    # TODO would be nice to start a request Session and
    # then loop over each category as "one" operation

    # / summer academies
    # these pages are queried by `Category:Event` and `Type:HDSA<year>`
    # it's not necessary to fetch the Type info now, as we are going to fetch
    # each page in the list on its own, therefore upon mapping over Event pages
    # we can "manually" pick them apart by Type:HDSA<year>

    with open("settings.toml", mode="rb") as fp:
        config = tomli.load(fp)

    cats = config['wiki']['categories']

    for cat in cats:
        results = get_category(cat)
        for r in results:
            print(f"r => {r}")

        print(f"cat:{cat} => {len(results)}")


# -- run everything
main()

# if __name__ == 'main':
#     main()
