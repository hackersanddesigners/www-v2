import sys
from httpwatcher import HttpWatcherServer
from tornado.ioloop import IOLoop
from build import build

root = sys.argv[1]

# print(root, port)

server = HttpWatcherServer(
  './wiki',                # serve files from the folder /path/to/html
  watch_paths=[
      "./styles",
      "./templates"
  ],                       # watch these paths for changes
  on_reload=build,         # copy styles to dist folder
  host="localhost",        # bind to host 127.0.0.1
  port=5020,               # bind to port 5556
  watcher_interval=1.0,    # maximum reload frequency (seconds)
  recursive=True,          # watch for changes in /path/to/html recursively
  open_browser=False       # automatically attempt to open a web browser (default: False for HttpWatcherServer)
)

server.listen()

try:
  # will keep serving until someone hits Ctrl+C
  IOLoop.current().start()
except KeyboardInterrupt:
  server.shutdown()
