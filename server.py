import redis

r = redis.Redis()

for key in r.scan_iter():
    print('k =>', key)

