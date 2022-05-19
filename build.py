import traceback
import json
import wikitextparser as wtp
from jinja2 import Environment, FileSystemLoader
from fetch import fetch_article
from parser import parser
from save import save, copy_styles

env = Environment(loader=FileSystemLoader('templates'), autoescape=True)


nav = [{
  'path': '/',
  'label': 'h&d',
},{
  'path': '/About',
  'label': 'about'
},{
  'path': '/Contact',
  'label': 'contact'
}]


static_pages = [
  'About',
  'Contact'
]

def build():

  copy_styles()

  for name in static_pages:
    try:
      page = fetch_article( name )
      article = parser( page )
      article['nav'] = nav
      save( article )
    except Exception as e:
      traceback.print_exc()

build()
