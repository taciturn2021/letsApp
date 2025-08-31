import datetime
from datetime import timezone
from bson import ObjectId
from app import mongo

class Call:
    """Call model for VOIP calling functionality."""
    
    @staticmethod
    def create_call_session(caller_id, callee_id, call_type="voice"):
        """Create a new call session"""
        call = {
            "caller_id": ObjectId(caller_id),
            "callee_id": ObjectId(callee_id),
            "call_type": call_type,  # "voice" or "video" (future)
            "status": "initiated",   # initiated, ringing, answered, ended, missed, declined
            "start_time": datetime.datetime.now(timezone.utc),
            "answer_time": None,
            "end_time": None,
            "duration": None,  # in seconds
            "quality_metrics": {
                "avg_latency": None,
                "packet_loss": None,
                "connection_quality": None
            },
            "created_at": datetime.datetime.now(timezone.utc),
            "updated_at": datetime.datetime.now(timezone.utc)
        }
        
        result = mongo.db.calls.insert_one(call)
        call["_id"] = result.inserted_id
        return call
    
    @staticmethod
    def get_by_id(call_id):
        """Get call by ID"""
        return mongo.db.calls.find_one({"_id": ObjectId(call_id)})
    
    @staticmethod
    def update_call_status(call_id, status, additional_data=None):
        """Update call status and related fields"""
        update_data = {
            "status": status,
            "updated_at": datetime.datetime.now(timezone.utc)
        }
        
        # Add specific timestamps based on status
        if status == "ringing":
            update_data["ring_time"] = datetime.datetime.now(timezone.utc)
        elif status == "answered":
            update_data["answer_time"] = datetime.datetime.now(timezone.utc)
        elif status in ["ended", "missed", "declined"]:
            update_data["end_time"] = datetime.datetime.now(timezone.utc)
            
            # Calculate duration if call was answered
            call = Call.get_by_id(call_id)
            if call and call.get("answer_time"):
                duration = (update_data["end_time"] - call["answer_time"]).total_seconds()
                update_data["duration"] = int(duration)
        
        # Add any additional data (like quality metrics)
        if additional_data:
            update_data.update(additional_data)
        
        result = mongo.db.calls.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def end_call(call_id, quality_metrics=None):
        """End a call and calculate duration"""
        try:
            call = Call.get_by_id(call_id)
            if not call:
                return False
            
            end_time = datetime.datetime.now(timezone.utc)
            update_data = {
                "status": "ended",
                "end_time": end_time,
                "updated_at": end_time
            }
            
            # Calculate duration if call was answered
            if call.get("answer_time"):
                duration = (end_time - call["answer_time"]).total_seconds()
                update_data["duration"] = int(duration)
            
            # Add quality metrics if provided
            if quality_metrics:
                update_data["quality_metrics"] = quality_metrics
            
            result = mongo.db.calls.update_one(
                {"_id": ObjectId(call_id)},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error ending call {call_id}: {e}")
            return False
    
    @staticmethod
    def get_user_call_history(user_id, limit=50, skip=0):
        """Get call history for a user"""
        user_obj_id = ObjectId(user_id)
        
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"caller_id": user_obj_id},
                        {"callee_id": user_obj_id}
                    ]
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "caller_id",
                    "foreignField": "_id",
                    "as": "caller_info"
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "callee_id",
                    "foreignField": "_id",
                    "as": "callee_info"
                }
            },
            {
                "$unwind": "$caller_info"
            },
            {
                "$unwind": "$callee_info"
            },
            {
                "$project": {
                    "call_type": 1,
                    "status": 1,
                    "start_time": 1,
                    "answer_time": 1,
                    "end_time": 1,
                    "duration": 1,
                    "quality_metrics": 1,
                    "caller": {
                        "id": "$caller_info._id",
                        "username": "$caller_info.username",
                        "full_name": "$caller_info.full_name",
                        "profile_picture": "$caller_info.profile_picture"
                    },
                    "callee": {
                        "id": "$callee_info._id",
                        "username": "$callee_info.username",
                        "full_name": "$callee_info.full_name",
                        "profile_picture": "$callee_info.profile_picture"
                    },
                    "is_incoming": {
                        "$eq": ["$callee_id", user_obj_id]
                    }
                }
            },
            {
                "$sort": {"start_time": -1}
            },
            {
                "$skip": skip
            },
            {
                "$limit": limit
            }
        ]
        
        return list(mongo.db.calls.aggregate(pipeline))
    
    @staticmethod
    def get_call_statistics(user_id):
        """Get call statistics for a user"""
        user_obj_id = ObjectId(user_id)
        
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"caller_id": user_obj_id},
                        {"callee_id": user_obj_id}
                    ]
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_calls": {"$sum": 1},
                    "answered_calls": {
                        "$sum": {"$cond": [{"$eq": ["$status", "answered"]}, 1, 0]}
                    },
                    "missed_calls": {
                        "$sum": {"$cond": [{"$eq": ["$status", "missed"]}, 1, 0]}
                    },
                    "declined_calls": {
                        "$sum": {"$cond": [{"$eq": ["$status", "declined"]}, 1, 0]}
                    },
                    "total_duration": {"$sum": "$duration"},
                    "avg_duration": {"$avg": "$duration"},
                    "incoming_calls": {
                        "$sum": {"$cond": [{"$eq": ["$callee_id", user_obj_id]}, 1, 0]}
                    },
                    "outgoing_calls": {
                        "$sum": {"$cond": [{"$eq": ["$caller_id", user_obj_id]}, 1, 0]}
                    }
                }
            }
        ]
        
        result = list(mongo.db.calls.aggregate(pipeline))
        return result[0] if result else {
            "total_calls": 0,
            "answered_calls": 0,
            "missed_calls": 0,
            "declined_calls": 0,
            "total_duration": 0,
            "avg_duration": 0,
            "incoming_calls": 0,
            "outgoing_calls": 0
        }
    
    @staticmethod
    def cleanup_old_calls(days_old=90):
        """Clean up old call records (optional maintenance)"""
        cutoff_date = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=days_old)
        
        result = mongo.db.calls.delete_many({
            "start_time": {"$lt": cutoff_date},
            "status": {"$in": ["missed", "declined", "ended"]}
        })
        
        return result.deleted_count