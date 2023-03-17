from jinja2 import Environment, FileSystemLoader
from slugify import slugify
from write_to_disk import main as write_to_disk

def make_url_slug(url: str):
    return slugify(url)


def make_index(articles):
    print('make-index =>', articles)
    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    env.filters['slug'] = make_url_slug
    t = env.get_template('index.html')

    article = {
        'title': 'Index',
        'slug': 'index',
        'articles': articles
    }

    document = t.render(article=article)
    write_to_disk(article['slug'], document)
