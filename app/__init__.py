import os
from flask import Flask
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from dotenv import load_dotenv

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
    )
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
        os.makedirs(app.config['UPLOAD_FOLDER'])
    except OSError:
        pass
    
    # Initialize extensions
    mongo.init_app(app)
    jwt.init_app(app)
    CORS(app)
    
    # Register blueprints
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Initialize Socket.IO (optional)
    socketio = None
    if with_socketio:
        try:
            from app.realtime import init_socketio
            socketio = init_socketio(app)
        except ImportError:
            print("SocketIO module not available, continuing without realtime features.")
    
    # Test route
    @app.route('/ping')
    def ping():
        return {"message": "pong", "status": "success"}
    
    return app
