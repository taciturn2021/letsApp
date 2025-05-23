import datetime
from bson import ObjectId
from app import mongo

class Call:
    """Call model for handling voice and video calls between users."""
    
    TYPE_VOICE = "voice"
    TYPE_VIDEO = "video"
    
    STATUS_INITIATED = "initiated"
    STATUS_RINGING = "ringing"
    STATUS_ONGOING = "ongoing"
    STATUS_ENDED = "ended"
    STATUS_MISSED = "missed"
    STATUS_REJECTED = "rejected"
    
    @staticmethod
    def initiate(caller_id, recipient_id, call_type=TYPE_VOICE, group_id=None):
        """
        Initiate a new call
        
        Parameters:
        - caller_id: ID of the user initiating the call
        - recipient_id: ID of the user receiving the call (None for group calls)
        - call_type: Type of call (voice or video)
        - group_id: Optional group ID for group calls
        """
        call_data = {
            "caller_id": ObjectId(caller_id),
            "call_type": call_type,
            "started_at": datetime.datetime.now(timezone.utc),
            "status": Call.STATUS_INITIATED,
            "ended_at": None,
            "duration": 0,  # Duration in seconds
            "metadata": {}
        }
        
        # Set recipient or group based on call type
        if group_id:
            call_data["group_id"] = ObjectId(group_id)
            call_data["participants"] = []  # Will be filled as users join
        else:
            call_data["recipient_id"] = ObjectId(recipient_id)
        
        result = mongo.db.calls.insert_one(call_data)
        call_data["_id"] = result.inserted_id
        
        return call_data
    
    @staticmethod
    def get_by_id(call_id):
        """Get call by ID"""
        return mongo.db.calls.find_one({"_id": ObjectId(call_id)})
    
    @staticmethod
    def update_status(call_id, status):
        """Update call status"""
        update_data = {
            "status": status,
        }
        
        # If call ended, update ended_at and calculate duration
        if status == Call.STATUS_ENDED or status == Call.STATUS_MISSED or status == Call.STATUS_REJECTED:
            now = datetime.datetime.now(timezone.utc)
            call = Call.get_by_id(call_id)
            
            if call and call["started_at"]:
                duration = (now - call["started_at"]).total_seconds()
                update_data["duration"] = int(duration)
                update_data["ended_at"] = now
        
        result = mongo.db.calls.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def add_participant(call_id, user_id, joined_at=None):
        """Add a participant to a group call"""
        if not joined_at:
            joined_at = datetime.datetime.now(timezone.utc)
            
        result = mongo.db.calls.update_one(
            {"_id": ObjectId(call_id)},
            {"$push": {"participants": {
                "user_id": ObjectId(user_id),
                "joined_at": joined_at,
                "left_at": None
            }}}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def remove_participant(call_id, user_id):
        """Mark a participant as having left a call"""
        now = datetime.datetime.now(timezone.utc)
        
        result = mongo.db.calls.update_one(
            {
                "_id": ObjectId(call_id),
                "participants.user_id": ObjectId(user_id)
            },
            {"$set": {"participants.$.left_at": now}}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def get_user_calls(user_id, limit=20, skip=0):
        """Get calls for a user with pagination"""
        query = {
            "$or": [
                {"caller_id": ObjectId(user_id)},
                {"recipient_id": ObjectId(user_id)},
                {"participants.user_id": ObjectId(user_id)}
            ]
        }
        
        return list(mongo.db.calls.find(query)
                   .sort("started_at", -1)
                   .skip(skip)
                   .limit(limit))
    
    @staticmethod
    def get_missed_calls(user_id, limit=20, skip=0):
        """Get missed calls for a user"""
        query = {
            "recipient_id": ObjectId(user_id),
            "status": Call.STATUS_MISSED
        }
        
        return list(mongo.db.calls.find(query)
                   .sort("started_at", -1)
                   .skip(skip)
                   .limit(limit))
                   
    @staticmethod
    def update_call_metadata(call_id, metadata):
        """Update call metadata (can store technical details about the call)"""
        result = mongo.db.calls.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": {"metadata": metadata}}
        )
        
        return result.modified_count > 0