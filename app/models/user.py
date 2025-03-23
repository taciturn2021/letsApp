import datetime
import bcrypt
import secrets
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
            },
            "password_history": [],
            "last_password_change": datetime.datetime.utcnow()
        }
        
        # Insert into database
        result = mongo.db.users.insert_one(user)
        user["_id"] = result.inserted_id
        
        # Remove password from returned object
        user.pop("password", None)
        user.pop("password_history", None)
        return user
    
    @staticmethod
    def get_by_id(user_id):
        """Get user by ID"""
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            user.pop("password", None)
            user.pop("password_history", None)
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
        
        # Check if the user is active
        if not user.get("is_active", True):
            return None
        
        # Check if the password matches
        if bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            user.pop("password", None)
            user.pop("password_history", None)
            return user
        
        return None
    
    @staticmethod
    def get_all(limit=100, skip=0):
        """Get all users with pagination"""
        return mongo.db.users.find({"is_active": True}).skip(skip).limit(limit)
    
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
        allowed_fields = ["full_name", "bio", "username", "email"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        # Check if username or email is being updated and ensure uniqueness
        if "username" in update_dict:
            existing = User.get_by_username(update_dict["username"])
            if existing and str(existing["_id"]) != user_id:
                return {"success": False, "message": "Username already taken"}
                
        if "email" in update_dict:
            existing = User.get_by_email(update_dict["email"])
            if existing and str(existing["_id"]) != user_id:
                return {"success": False, "message": "Email already registered"}
        
        if update_dict:
            update_dict["updated_at"] = datetime.datetime.utcnow()
            
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_dict}
            )
            
            return {"success": result.modified_count > 0, "message": "Profile updated successfully"}
        
        return {"success": False, "message": "No valid fields to update"}
    
    @staticmethod
    def update_settings(user_id, settings):
        """Update user settings"""
        allowed_settings = ["notifications_enabled", "read_receipts_enabled", "typing_indicators_enabled"]
        update_dict = {f"settings.{k}": v for k, v in settings.items() if k in allowed_settings}
        
        if update_dict:
            update_dict["updated_at"] = datetime.datetime.utcnow()
            
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_dict}
            )
            
            return {"success": result.modified_count > 0, "message": "Settings updated successfully"}
        
        return {"success": False, "message": "No valid settings to update"}
    
    @staticmethod
    def get_settings(user_id):
        """Get user settings"""
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)}, {"settings": 1})
        return user.get("settings", {}) if user else {}
    
    @staticmethod
    def change_password(user_id, current_password, new_password):
        """Change user password"""
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), user["password"]):
            return {"success": False, "message": "Current password is incorrect"}
        
        # Check if new password is in password history (last 5 passwords)
        password_history = user.get("password_history", [])
        for old_password in password_history:
            if bcrypt.checkpw(new_password.encode('utf-8'), old_password):
                return {"success": False, "message": "New password cannot be the same as any of your last 5 passwords"}
        
        # Hash the new password
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update password history (keep last 5)
        if len(password_history) >= 5:
            password_history.pop(0)  # Remove oldest password
        password_history.append(user["password"])  # Add current password to history
        
        # Update the password
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "password": new_hashed_password,
                    "password_history": password_history,
                    "last_password_change": datetime.datetime.utcnow(),
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        return {"success": result.modified_count > 0, "message": "Password changed successfully"}
    
    @staticmethod
    def generate_reset_token(email):
        """Generate a password reset token"""
        user = User.get_by_email(email)
        
        if not user:
            # Still return success to prevent user enumeration
            return {"success": True, "message": "If an account with this email exists, a password reset link has been sent"}
        
        # Generate a token
        token = secrets.token_urlsafe(32)
        expiry = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        
        # Store the token in the database
        mongo.db.password_reset_tokens.delete_many({"user_id": user["_id"]})  # Delete any existing tokens
        mongo.db.password_reset_tokens.insert_one({
            "user_id": user["_id"],
            "token": token,
            "expiry": expiry,
            "created_at": datetime.datetime.utcnow()
        })
        
        # In a real application, send an email with the token here
        # For demo purposes, just return success
        return {
            "success": True, 
            "message": "If an account with this email exists, a password reset link has been sent",
            "token": token  # Only for demonstration, would normally be sent via email
        }
    
    @staticmethod
    def reset_password(token, new_password):
        """Reset a user's password using a token"""
        # Find the token
        token_doc = mongo.db.password_reset_tokens.find_one({
            "token": token,
            "expiry": {"$gt": datetime.datetime.utcnow()}
        })
        
        if not token_doc:
            return {"success": False, "message": "Invalid or expired token"}
        
        # Find the user
        user = mongo.db.users.find_one({"_id": token_doc["user_id"]})
        
        if not user:
            return {"success": False, "message": "User not found"}
        
        # Hash the new password
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update password history (keep last 5)
        password_history = user.get("password_history", [])
        if len(password_history) >= 5:
            password_history.pop(0)  # Remove oldest password
        password_history.append(user["password"])  # Add current password to history
        
        # Update the password
        result = mongo.db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "password": new_hashed_password,
                    "password_history": password_history,
                    "last_password_change": datetime.datetime.utcnow(),
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        # Delete the token to prevent reuse
        mongo.db.password_reset_tokens.delete_one({"_id": token_doc["_id"]})
        
        return {"success": result.modified_count > 0, "message": "Password has been reset successfully"}
    
    @staticmethod
    def update_profile_picture(user_id, media_id):
        """Update a user's profile picture"""
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "profile_picture": str(media_id),
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return {"success": result.modified_count > 0, "message": "Profile picture updated successfully"}
    
    @staticmethod
    def remove_profile_picture(user_id):
        """Remove a user's profile picture"""
        result = mongo.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "profile_picture": None,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        return {"success": result.modified_count > 0, "message": "Profile picture removed successfully"}
