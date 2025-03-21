from flask_socketio import SocketIO

socketio = SocketIO()

def init_socketio(app):
    """Initialize SocketIO extension"""
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Import socket event handlers
    from app.realtime import events
    from app.realtime import presence
    from app.realtime import typing
    
    return socketio
