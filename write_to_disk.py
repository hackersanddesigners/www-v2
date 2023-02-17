def main(article: str, document):

    with open('./wiki/%s.html' % article['slug'], 'w') as f:

        try:
            f.write(document)
            print('✓ %s-article "%s" has been correctly written to disk'
                  % (article['slug'], article['title']))
        except Exception as e:
            print('✕ error for %s-article "%s" =>'
                  % (article['slug'], article['title']), e)
