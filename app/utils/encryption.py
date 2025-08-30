"""
Encryption utilities for sensitive data like API keys
"""
import os
import base64
import binascii
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from flask import current_app

class EncryptionManager:
    """Manager for encrypting and decrypting sensitive data"""
    
    @staticmethod
    def _get_key():
        """Generate or retrieve encryption key from app secret"""
        # Use the app's SECRET_KEY as the basis for our encryption key
        secret_key = current_app.config.get('SECRET_KEY', 'dev_key').encode()
        
        # Generate a consistent salt based on the secret key
        salt = secret_key[:16].ljust(16, b'0')
        
        # Derive a proper encryption key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key))
        return key
    
    @staticmethod
    def encrypt(data):
        """
        Encrypt sensitive data like API keys
        
        Args:
            data (str): The data to encrypt
            
        Returns:
            str: Base64 encoded encrypted data
        """
        if not data:
            return None
            
        try:
            key = EncryptionManager._get_key()
            fernet = Fernet(key)
            
            # Encrypt the data
            encrypted_data = fernet.encrypt(data.encode())
            
            # Return base64 encoded string for storage
            return base64.urlsafe_b64encode(encrypted_data).decode()
            
        except Exception as e:
            current_app.logger.error(f"Encryption error: {str(e)}")
            raise Exception("Failed to encrypt data")
    
    @staticmethod
    def decrypt(encrypted_data):
        """
        Decrypt sensitive data like API keys
        
        Args:
            encrypted_data (str): Base64 encoded encrypted data
            
        Returns:
            str: Decrypted data
        """
        if not encrypted_data:
            return None
            
        try:
            key = EncryptionManager._get_key()
            fernet = Fernet(key)
            
            # Decode from base64
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode())
            
            # Decrypt the data
            decrypted_data = fernet.decrypt(decoded_data)
            
            return decrypted_data.decode()
            
        except binascii.Error as e:
            current_app.logger.error(f"Base64 decoding error: {str(e)}")
            raise Exception("Invalid base64 encoded data")
        except Exception as e:
            current_app.logger.error(f"Decryption error: {str(e)}")
            current_app.logger.error(f"Encrypted data length: {len(encrypted_data) if encrypted_data else 'None'}")
            current_app.logger.error(f"First 50 chars: {encrypted_data[:50] if encrypted_data else 'None'}")
            raise Exception("Failed to decrypt data")
