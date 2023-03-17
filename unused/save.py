import shutil
import os
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'), autoescape=True)

def copy_styles ():
  root_styles = './styles'
  dist_styles = './wiki/assets/styles'

  if os.path.exists(dist_styles):
    shutil.rmtree(dist_styles)

  shutil.copytree(root_styles, dist_styles)


def save (article):

  t = env.get_template('article.html')
  document = t.render(article=article)

  with open('./wiki/%s.html' % article['slug'], 'w') as f:

    try:
        f.write(document)
        print('✓ %s-article "%s" has been correctly written to disk' % (article['slug'], article['title']))

    except Exception as e:
        print('✕ error for %s-article "%s" =>' % (article['slug'], article['title']), e)
