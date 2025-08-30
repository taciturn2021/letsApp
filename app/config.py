import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/letsapp')
    
    # JWT Configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt_dev_key')
    JWT_ACCESS_TOKEN_EXPIRES = 86400  # 24 hours
    
    # Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp3', 'mp4', 'doc', 'docx'}
    
    # Rate Limiting
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # Encryption Configuration (using SECRET_KEY as base)
    # This ensures consistent encryption key across app restarts
    
    # Gemini Configuration (replaces OpenAI)
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    MONGO_URI = "mongodb://localhost:27017/letsapp_test"

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, these would be set by environment variables

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
