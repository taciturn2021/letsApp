from app import create_app
from app.utils.db import init_db
import os
from flask_socketio import SocketIO
from app.realtime import socketio

# Create app without SocketIO for a basic server focused on MongoDB models
app = create_app(with_socketio=False)
port = int(os.environ.get("PORT", 5001))

if __name__ == "__main__":
    init_db(app)  # Ensure indexes are created
    app.run(host="0.0.0.0", port=port)
    socketio.run(app, host="0.0.0.0", port=5000)
    print("Listening on ", port)
    print("SocketIO running on port 5001")
    print("Flask app running on port", port)