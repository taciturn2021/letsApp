from app import mongo
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

def get_db():
    """Helper function to get the database instance."""
    return mongo.db

def init_db(app):
    """Initialize database with required indexes."""
    with app.app_context():
        db = get_db()
        
        # Create indexes for users collection
        db.users.create_indexes([
            IndexModel([("email", ASCENDING)], unique=True),
            IndexModel([("username", ASCENDING)], unique=True),
            IndexModel([("last_seen", DESCENDING)])
        ])
        
        # Create indexes for messages collection
        db.messages.create_indexes([
            IndexModel([("sender_id", ASCENDING)]),
            IndexModel([("recipient_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("content", TEXT)])
        ])
        
        # Create indexes for conversations (for quick message loading)
        db.messages.create_indexes([
            IndexModel([
                ("sender_id", ASCENDING), 
                ("recipient_id", ASCENDING), 
                ("created_at", DESCENDING)
            ]),
            IndexModel([
                ("recipient_id", ASCENDING), 
                ("sender_id", ASCENDING), 
                ("created_at", DESCENDING)
            ])
        ])
        
        # Create indexes for groups collection
        db.groups.create_indexes([
            IndexModel([("name", TEXT)]),
            IndexModel([("members", ASCENDING)])
        ])
        
        # Create indexes for group_messages collection
        db.group_messages.create_indexes([
            IndexModel([("group_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel([("sender_id", ASCENDING)]),
            IndexModel([("content", TEXT)])
        ])
        
        # Create indexes for files collection
        db.files.create_indexes([
            IndexModel([("uploader_id", ASCENDING)]),
            IndexModel([("message_id", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)])
        ])
        
        # Create indexes for message_reactions collection
        db.message_reactions.create_indexes([
            IndexModel([("message_id", ASCENDING)]),
            IndexModel([("user_id", ASCENDING)])
        ])
        
        # Create indexes for contacts collection
        db.contacts.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("contact_id", ASCENDING)])
        ])
        
        # Create indexes for presence collection
        db.presence.create_indexes([
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("last_updated", DESCENDING)])
        ])
        
        print("Database indexes created successfully")
