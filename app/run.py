#!/opt/licman/python/bin/python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.server import create_app, socketio

app = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=58080, allow_unsafe_werkzeug=True)
