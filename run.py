from app import create_app
from app.utils.db import init_db

# Create app without SocketIO for a basic server focused on MongoDB models
app = create_app(with_socketio=False)
port = 5001
if __name__ == "__main__":
    init_db(app)  # Ensure indexes are created
    app.run(host="0.0.0.0", port=port)
    print("Listening on ", port)
