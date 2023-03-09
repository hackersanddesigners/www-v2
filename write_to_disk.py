def main(page_slug: str, document: str):

    with open('./wiki/%s.html' % page_slug, 'w') as f:

        try:
            f.write(document)
            print('✓ %s-article has been correctly written to disk' % page_slug)
        except Exception as e:
            print('✕ error for %s-article "%s" =>' % page_slug, e)
