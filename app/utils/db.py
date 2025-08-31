from app import mongo
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

def get_db():
    """Helper function to get the database instance."""
    return mongo.db

def init_db(app):
    """Initialize database with required indexes and setup for advanced features."""
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
            IndexModel([("content", TEXT)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("room_id", ASCENDING)])
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
            IndexModel([("members", ASCENDING)]),
            IndexModel([("version", ASCENDING)])  # For optimistic locking
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
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("file_type", ASCENDING)])
        ])
        
        # Create indexes for message_reactions collection
        db.message_reactions.create_indexes([
            IndexModel([("message_id", ASCENDING)]),
            IndexModel([("user_id", ASCENDING)])
        ])
        
        # Create indexes for contacts collection
        db.contacts.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("contact_id", ASCENDING)]),
            IndexModel([("status", ASCENDING)])
        ])
        
        # Create indexes for presence collection
        db.presence.create_indexes([
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)]),
            IndexModel([("last_updated", DESCENDING)])
        ])
        
        # Create indexes for calls collection
        db.calls.create_indexes([
            IndexModel([("caller_id", ASCENDING)]),
            IndexModel([("callee_id", ASCENDING)]),
            IndexModel([("start_time", DESCENDING)]),
            IndexModel([("status", ASCENDING)]),
            IndexModel([("call_type", ASCENDING)]),
            IndexModel([
                ("caller_id", ASCENDING), 
                ("callee_id", ASCENDING), 
                ("start_time", DESCENDING)
            ]),
            IndexModel([
                ("callee_id", ASCENDING), 
                ("status", ASCENDING), 
                ("start_time", DESCENDING)
            ])  # For missed calls queries
        ])
        
        # Create indexes for audit and logging collections
        db.user_audit_log.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("timestamp", DESCENDING)]),
            IndexModel([("action", ASCENDING)])
        ])
        
        db.user_settings_log.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("timestamp", DESCENDING)])
        ])
        
        db.security_audit_log.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("timestamp", DESCENDING)]),
            IndexModel([("action", ASCENDING)])
        ])
        
        db.user_sessions.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("is_valid", ASCENDING)])
        ])
        
        db.notifications.create_indexes([
            IndexModel([("user_id", ASCENDING)]),
            IndexModel([("is_read", ASCENDING)]),
            IndexModel([("created_at", DESCENDING)])
        ])
        
        print("Database indexes created successfully")
        
        # Add version field to existing groups for optimistic locking
        update_groups_for_concurrency_control(db)
        
        # Create database views for analytics
        create_analytics_views(db)

def update_groups_for_concurrency_control(db):
    """Add version field to existing groups that don't have it."""
    try:
        # Update groups that don't have a version field
        result = db.groups.update_many(
            {"version": {"$exists": False}},
            {"$set": {"version": 1}}
        )
        
        if result.modified_count > 0:
            print(f"Added version field to {result.modified_count} existing groups")
        else:
            print("All groups already have version field for concurrency control")
            
    except Exception as e:
        print(f"Error updating groups for concurrency control: {e}")

def create_analytics_views(db):
    """Create database views for enhanced analytics."""
    try:
        from app.models.views import DatabaseViews
        
        print("Creating analytics views...")
        results = DatabaseViews.create_all_views()
        
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"Analytics views created: {success_count}/{total_count} successful")
        
        if success_count < total_count:
            failed_views = [name for name, success in results.items() if not success]
            print(f"Failed to create views: {failed_views}")
            
    except Exception as e:
        print(f"Error creating analytics views: {e}")
        print("Views will need to be created manually using /analytics/views/create endpoint")
