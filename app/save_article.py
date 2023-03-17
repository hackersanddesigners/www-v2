from jinja2 import Environment, FileSystemLoader
from make_article import make_article
from write_to_disk import main as write_to_disk

def x(article_title):
    article = make_article(article_title)

    env = Environment(loader=FileSystemLoader('app/templates'), autoescape=True)
    t = env.get_template('article.html')
    document = t.render(article=article)

    write_to_disk(article['slug'], document)
