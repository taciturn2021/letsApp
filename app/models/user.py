import datetime
import bcrypt
import secrets
from bson import ObjectId
from app import mongo
from app.models.media import Media
import logging

logger = logging.getLogger(__name__)

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
        """Update user profile information with transaction support"""
        allowed_fields = ["full_name", "bio", "username", "email"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not update_dict:
            return {"success": False, "message": "No valid fields to update"}
        
        # Start a transaction for atomic updates
        with mongo.cx.start_session() as session:
            with session.start_transaction():
                try:
                    # Check if username or email is being updated and ensure uniqueness
                    if "username" in update_dict:
                        existing = mongo.db.users.find_one(
                            {"username": update_dict["username"]}, 
                            session=session
                        )
                        if existing and str(existing["_id"]) != user_id:
                            session.abort_transaction()
                            return {"success": False, "message": "Username already taken"}
                            
                    if "email" in update_dict:
                        existing = mongo.db.users.find_one(
                            {"email": update_dict["email"]}, 
                            session=session
                        )
                        if existing and str(existing["_id"]) != user_id:
                            session.abort_transaction()
                            return {"success": False, "message": "Email already registered"}
                    
                    # Add timestamp
                    update_dict["updated_at"] = datetime.datetime.utcnow()
                    
                    # Update user profile
                    result = mongo.db.users.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": update_dict},
                        session=session
                    )
                    
                    if result.modified_count == 0:
                        session.abort_transaction()
                        return {"success": False, "message": "User not found or no changes made"}
                    
                    # Log the profile update in audit trail
                    audit_entry = {
                        "user_id": ObjectId(user_id),
                        "action": "profile_update",
                        "fields_updated": list(update_dict.keys()),
                        "timestamp": datetime.datetime.utcnow(),
                        "ip_address": None,  # Could be passed from request context
                        "user_agent": None   # Could be passed from request context
                    }
                    
                    mongo.db.user_audit_log.insert_one(audit_entry, session=session)
                    
                    # Commit the transaction
                    session.commit_transaction()
                    return {"success": True, "message": "Profile updated successfully"}
                    
                except Exception as e:
                    session.abort_transaction()
                    return {"success": False, "message": f"Error updating profile: {str(e)}"}
    
    @staticmethod
    def update_settings(user_id, settings):
        """Update user settings with transaction support"""
        allowed_settings = ["notifications_enabled", "read_receipts_enabled", "typing_indicators_enabled"]
        update_dict = {f"settings.{k}": v for k, v in settings.items() if k in allowed_settings}
        
        if not update_dict:
            return {"success": False, "message": "No valid settings to update"}
        
        # Start a transaction for atomic updates
        with mongo.cx.start_session() as session:
            with session.start_transaction():
                try:
                    # Get current user settings for comparison
                    current_user = mongo.db.users.find_one(
                        {"_id": ObjectId(user_id)}, 
                        {"settings": 1},
                        session=session
                    )
                    
                    if not current_user:
                        session.abort_transaction()
                        return {"success": False, "message": "User not found"}
                    
                    current_settings = current_user.get("settings", {})
                    
                    # Add timestamp
                    update_dict["updated_at"] = datetime.datetime.utcnow()
                    
                    # Update user settings
                    result = mongo.db.users.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": update_dict},
                        session=session
                    )
                    
                    if result.modified_count == 0:
                        session.abort_transaction()
                        return {"success": False, "message": "No changes made to settings"}
                    
                    # Create settings change log entry
                    changes = {}
                    for key, value in settings.items():
                        if key in allowed_settings:
                            old_value = current_settings.get(key)
                            if old_value != value:
                                changes[key] = {"old": old_value, "new": value}
                    
                    if changes:
                        settings_log_entry = {
                            "user_id": ObjectId(user_id),
                            "action": "settings_update",
                            "changes": changes,
                            "timestamp": datetime.datetime.utcnow(),
                            "ip_address": None,  # Could be passed from request context
                            "user_agent": None   # Could be passed from request context
                        }
                        
                        mongo.db.user_settings_log.insert_one(settings_log_entry, session=session)
                    
                    # If notifications were disabled, mark all pending notifications as dismissed
                    if "notifications_enabled" in settings and not settings["notifications_enabled"]:
                        mongo.db.notifications.update_many(
                            {
                                "user_id": ObjectId(user_id),
                                "is_read": False
                            },
                            {
                                "$set": {
                                    "is_dismissed": True,
                                    "dismissed_at": datetime.datetime.utcnow()
                                }
                            },
                            session=session
                        )
                    
                    # Commit the transaction
                    session.commit_transaction()
                    return {"success": True, "message": "Settings updated successfully"}
                    
                except Exception as e:
                    session.abort_transaction()
                    return {"success": False, "message": f"Error updating settings: {str(e)}"}
    
    @staticmethod
    def get_settings(user_id):
        """Get user settings"""
        user = mongo.db.users.find_one({"_id": ObjectId(user_id)}, {"settings": 1})
        return user.get("settings", {}) if user else {}
    
    @staticmethod
    def change_password_with_transaction(user_id, current_password, new_password):
        """Change user password with full transaction support"""
        # Start a transaction for atomic password change
        with mongo.cx.start_session() as session:
            with session.start_transaction():
                try:
                    # Get user with current password and history
                    user = mongo.db.users.find_one(
                        {"_id": ObjectId(user_id)}, 
                        session=session
                    )
                    
                    if not user:
                        session.abort_transaction()
                        return {"success": False, "message": "User not found"}
                    
                    # Verify current password
                    if not bcrypt.checkpw(current_password.encode('utf-8'), user["password"]):
                        session.abort_transaction()
                        return {"success": False, "message": "Current password is incorrect"}
                    
                    # Check if new password is in password history (last 5 passwords)
                    password_history = user.get("password_history", [])
                    for old_password in password_history:
                        if bcrypt.checkpw(new_password.encode('utf-8'), old_password):
                            session.abort_transaction()
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
                        },
                        session=session
                    )
                    
                    if result.modified_count == 0:
                        session.abort_transaction()
                        return {"success": False, "message": "Failed to update password"}
                    
                    # Log the password change in security audit
                    security_log_entry = {
                        "user_id": ObjectId(user_id),
                        "action": "password_change",
                        "timestamp": datetime.datetime.utcnow(),
                        "ip_address": None,  # Could be passed from request context
                        "user_agent": None,  # Could be passed from request context
                        "success": True
                    }
                    
                    mongo.db.security_audit_log.insert_one(security_log_entry, session=session)
                    
                    # Invalidate all existing sessions for this user (security measure)
                    mongo.db.user_sessions.update_many(
                        {"user_id": ObjectId(user_id)},
                        {
                            "$set": {
                                "is_valid": False,
                                "invalidated_at": datetime.datetime.utcnow(),
                                "invalidation_reason": "password_change"
                            }
                        },
                        session=session
                    )
                    
                    # Commit the transaction
                    session.commit_transaction()
                    return {"success": True, "message": "Password changed successfully. Please log in again."}
                    
                except Exception as e:
                    session.abort_transaction()
                    return {"success": False, "message": f"Error changing password: {str(e)}"}

    @staticmethod
    def change_password(user_id, current_password, new_password):
        """Change user password (legacy method - calls transaction version)"""
        return User.change_password_with_transaction(user_id, current_password, new_password)
    
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
        """Update user's profile picture"""
        try:
            # Verify the media exists
            media = Media.get_by_id(media_id)
            if not media:
                return {"success": False, "message": "Media not found"}
            
            # Update the user's profile
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "profile_picture": media_id,
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
            
            return {"success": result.modified_count > 0, "message": "Profile picture updated successfully"}
        except Exception as e:
            return {"success": False, "message": f"Error updating profile picture: {str(e)}"}
    
    @staticmethod
    def remove_profile_picture(user_id):
        """Remove user's profile picture reference"""
        try:
            # First get the current profile picture ID
            user = User.get_by_id(user_id)
            if not user or not user.get("profile_picture"):
                return {"success": False, "message": "No profile picture to remove"}
            
            # Update the user document to remove the profile picture reference
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$unset": {
                        "profile_picture": ""
                    },
                    "$set": {
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
            
            # Note: We're not deleting the actual media from GridFS 
            # as it might be referenced elsewhere or needed for history
            return {"success": result.modified_count > 0, "message": "Profile picture removed successfully"}
        except Exception as e:
            return {"success": False, "message": f"Error removing profile picture: {str(e)}"}
    
    @staticmethod
    def update_api_key(user_id, api_key):
        """Update user's API key with encryption"""
        try:
            from app.utils.encryption import EncryptionManager
            
            # Encrypt the API key before storing
            encrypted_api_key = EncryptionManager.encrypt(api_key)
            
            # Update the user's API key
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "api_key": encrypted_api_key,
                        "api_key_updated_at": datetime.datetime.utcnow(),
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                logger.warning(f"Failed to update API key for user {user_id}")
                return {"success": False, "message": "User not found or no changes made"}
            
            # Log the API key update in audit trail
            audit_entry = {
                "user_id": ObjectId(user_id),
                "action": "api_key_update",
                "timestamp": datetime.datetime.utcnow(),
                "ip_address": None,  # Could be passed from request context
                "user_agent": None   # Could be passed from request context
            }
            
            mongo.db.user_audit_log.insert_one(audit_entry)
            logger.info(f"API key updated for user {user_id}")
            
            return {"success": True, "message": "API key updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating API key for user {user_id}: {str(e)}")
            return {"success": False, "message": f"Error updating API key: {str(e)}"}
    
    @staticmethod
    def get_api_key(user_id):
        """Get and decrypt user's API key"""
        try:
            from app.utils.encryption import EncryptionManager
            
            user = mongo.db.users.find_one(
                {"_id": ObjectId(user_id)}, 
                {"api_key": 1}
            )
            
            if not user or not user.get("api_key"):
                return None
            
            # Try to decrypt the API key
            try:
                decrypted_api_key = EncryptionManager.decrypt(user["api_key"])
                return decrypted_api_key
            except Exception as decrypt_error:
                # If decryption fails, the API key is corrupted or was encrypted with a different key
                logger.warning(f"Failed to decrypt API key for user {user_id}, removing corrupted key: {str(decrypt_error)}")
                
                # Remove the corrupted API key from the database
                mongo.db.users.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$unset": {"api_key": "", "api_key_updated_at": ""}}
                )
                
                return None
            
        except Exception as e:
            logger.error(f"Error getting API key for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def remove_api_key(user_id):
        """Remove user's API key"""
        try:
            # Update the user document to remove the API key
            result = mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$unset": {
                        "api_key": "",
                        "api_key_updated_at": ""
                    },
                    "$set": {
                        "updated_at": datetime.datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count == 0:
                return {"success": False, "message": "User not found or no API key to remove"}
            
            # Log the API key removal in audit trail
            audit_entry = {
                "user_id": ObjectId(user_id),
                "action": "api_key_removal",
                "timestamp": datetime.datetime.utcnow(),
                "ip_address": None,  # Could be passed from request context
                "user_agent": None   # Could be passed from request context
            }
            
            mongo.db.user_audit_log.insert_one(audit_entry)
            
            return {"success": True, "message": "API key removed successfully"}
            
        except Exception as e:
            return {"success": False, "message": f"Error removing API key: {str(e)}"}
