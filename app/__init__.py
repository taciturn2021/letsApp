import os
from flask import Flask
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

mongo = PyMongo()
jwt = JWTManager()

def create_app(test_config=None, with_socketio=True):
    # Load environment variables
    load_dotenv()
    
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev_key'),
        MONGO_URI=os.environ.get('MONGO_URI', 'mongodb://localhost:27017/letsapp'),
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'jwt_dev_key'),
        JWT_ACCESS_TOKEN_EXPIRES=86400,  # 24 hours
        UPLOAD_FOLDER=os.path.join(app.instance_path, 'uploads'),
        FRONTEND=os.environ.get('FRONTEND', 'http://localhost:3000')
    )
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
        os.makedirs(app.config['UPLOAD_FOLDER'])
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile_pictures'))
    except OSError:
        pass
    
    # Initialize extensions
    mongo.init_app(app)
    jwt.init_app(app)
    
    frontend_origin = app.config['FRONTEND']
    print(f"CORS is configured for origin: {frontend_origin}")

# Replace the existing CORS configuration with this more permissive one for development
    CORS(app, 
     origins=[frontend_origin, "http://localhost:3787"],  # Explicitly add both origins
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)
    
    #configure Flask-Limiter
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200000 per day", "5000 per hour"]
    )
    
    # Register blueprints
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.api.user_routes import bp as users_bp
    app.register_blueprint(users_bp, url_prefix='/api/users')
    
    from app.api.routes import bp as load_bp
    app.register_blueprint(load_bp, url_prefix='/api/load')
    
    from app.api.messages_routes import bp as messages_bp
    app.register_blueprint(messages_bp, url_prefix='/api/messages')
    
    from app.api.media_routes import bp as media_bp
    app.register_blueprint(media_bp, url_prefix='/api/media')
    
    # Test route
    @app.route('/ping')
    def ping():
        return {"message": "pong", "status": "success"}
    
    # Initialize Socket.IO only after app is fully set up
    socketio = None
    if with_socketio:
        try:
            # Use a more specific exception handler to diagnose problems
            from flask_socketio import SocketIO
            
            # Create SocketIO instance
            socketio = SocketIO()
            socketio.init_app(app, cors_allowed_origins=[app.config['FRONTEND']])
            
            # Register all socket event handlers
            from app.realtime.events import register_handlers as register_events
            register_events(socketio)
            
            from app.realtime.presence import register_handlers as register_presence
            register_presence(socketio)
            
            from app.realtime.typing import register_handlers as register_typing
            register_typing(socketio)
            
            from app.realtime.chat import register_handlers as register_chat
            register_chat(socketio)
            
            print("SocketIO initialized successfully")
        except Exception as e:
            print(f"SocketIO initialization failed: {str(e)}")
    
    return app