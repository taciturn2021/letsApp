from app import create_app
from app.utils.db import init_db
import os

# Create app WITH SocketIO enabled
app = create_app(with_socketio=True)
port = int(os.environ.get("PORT", 5001))

if __name__ == "__main__":
    init_db(app)  # Ensure indexes are created
    print(f"Starting server with SocketIO on port {port}")

    
    # Get the SocketIO instance from our app
    # It's already set up in create_app, just need to import it
    from flask_socketio import SocketIO
    socketio = app.extensions.get('socketio')
    
    if not socketio:
        print("ERROR: SocketIO not properly initialized!")
        # Create a new instance if needed as fallback
        socketio = SocketIO(app)
    
    # Run the SocketIO server
    socketio.run(app, host="0.0.0.0", port=port, debug=True)