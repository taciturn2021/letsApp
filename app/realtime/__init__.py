# Export the socketio instance initialization function
# But don't define socketio here to avoid circular imports

def get_socketio():
    """Get the SocketIO instance from the current Flask app"""
    from flask import current_app
    return current_app.extensions.get('socketio')
