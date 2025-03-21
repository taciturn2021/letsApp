import datetime
import bcrypt
from bson import ObjectId
from app import mongo

class User:
    """User model for authentication and profile management."""
    
    @staticmethod
    def create(username, email, password, full_name=None, profile_picture=None):
        """
        Create a new user with hashed password
        """
        # Hash the password with bcrypt
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Prepare user document
        user = {
            "username": username,
            "email": email,
            "password": hashed_password,
            "full_name": full_name,
            "profile_picture": profile_picture,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "last_seen": datetime.datetime.utcnow(),
            "is_active": True,
            "bio": "",
            "settings": {
                "notifications_enabled": True,
                "read_receipts_enabled": True,
                "typing_indicators_enabled": True
            }
        }
        
        # Insert into database
        result = mongo.db.users.insert_one(user)
        user["_id"] = result.inserted_id
        
        # Remove password from returned object
        user.pop("password", None)
        return user
    
    @staticmethod
    def get_by_id(user_id):
        """Get user by ID"""
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user.pop("password", None)
        return user
    
    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        return mongo.db.users.find_one({"email": email})
    
    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        return mongo.db.users.find_one({"username": username})
    
    @staticmethod
    def authenticate(email, password):
        """Authenticate user with email and password"""
        user = User.get_by_email(email)
        
        if not user:
            return None
        
        # Check if the password matches
        if bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            user.pop("password", None)
            return user
        
        return None
    
    @staticmethod
    def get_all(limit=100, skip=0):
        """Get all users with pagination"""
        return mongo.db.users.find().skip(skip).limit(limit)
    
    @staticmethod
    def update_last_seen(user_id):
        """Update the last_seen timestamp for a user"""
        mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_seen": datetime.datetime.utcnow()}}
        )
    
    @staticmethod
    def update_profile(user_id, update_data):
        """Update user profile information"""
        allowed_fields = ["full_name", "bio", "profile_picture", "settings"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if update_dict:
            update_dict["updated_at"] = datetime.datetime.utcnow()
            
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_dict}
            )
            
            return result.modified_count > 0
        
        return False
