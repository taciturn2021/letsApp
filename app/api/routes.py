from flask import jsonify, request, Blueprint, render_template
from app.api import bp
from app.models import User, Message, Group, GroupMessage, Contact, File, Presence
from app.models.presence import Presence
from app.models.views import DatabaseViews
from bson import ObjectId
import datetime
from datetime import timezone
import json


bp = Blueprint('load', __name__)

def serialize_datetime(obj):
    """Convert datetime objects to ISO format strings"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    elif isinstance(obj, list):
        return [serialize_datetime(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: serialize_datetime(value) for key, value in obj.items()}
    return obj

@bp.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "API is running"})

@bp.route('/all_users', methods=['GET'])
def get_users():
    """Get all users (demonstration endpoint)"""
    print(f"Request from host: {request.remote_addr}, port: {request.environ.get('REMOTE_PORT', 'unknown')}")
    users = list(User.get_all())
    
    # Remove passwords from the response and add presence data
    for user in users:
        if 'password' in user:
            del user['password']
        
        # Add consistent ID format for frontend compatibility
        user['id'] = str(user.get('_id'))
        
        # Add presence status
        user_id = str(user.get('_id'))
        user['status'] = Presence.get_status(user_id)
        
    print(f"Returning {len(users)} users with presence status")
    return jsonify({"users": users})

# Enhanced Analytics Endpoints using Database Views
from app import mongo

@bp.route('/analytics/user_stats', methods=['GET'])
def user_stats():
    """Get enhanced user statistics using database views"""
    # Basic user counts
    total_users = mongo.db.users.count_documents({})
    active_users = mongo.db.users.count_documents({"is_active": True})
    
    # Get users registered in the last 30 days
    thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
    new_users = mongo.db.users.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Get users active in the last 24 hours
    day_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)
    active_today = mongo.db.users.count_documents({"last_seen": {"$gte": day_ago}})
    
    # Get enhanced user activity data from view
    try:
        user_activity_data = DatabaseViews.get_view_data("user_activity_summary", limit=10)
        top_users = [
            {
                "username": user.get("username", "Unknown"),
                "total_messages": user.get("total_messages", 0),
                "messages_per_day": user.get("messages_per_day", 0),
                "active_days": user.get("active_days", 0)
            }
            for user in user_activity_data
        ]
    except Exception as e:
        print(f"Error getting user activity data: {e}")
        top_users = []
    
    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "new_users_last_30_days": new_users,
        "active_users_last_24h": active_today,
        "top_active_users": top_users
    })

@bp.route('/analytics/message_stats', methods=['GET'])
def message_stats():
    """Get enhanced message statistics using database views and aggregation pipelines"""
    total_messages = mongo.db.messages.count_documents({})
    total_group_messages = mongo.db.group_messages.count_documents({})
    
    # Get messages sent in the last 30 days
    thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
    recent_messages = mongo.db.messages.count_documents({"created_at": {"$gte": thirty_days_ago}})
    recent_group_messages = mongo.db.group_messages.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Enhanced daily message counts using aggregation pipeline
    pipeline = [
        {"$match": {"created_at": {"$gte": thirty_days_ago}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_messages = list(mongo.db.messages.aggregate(pipeline))
    daily_group_messages = list(mongo.db.group_messages.aggregate(pipeline))
    
    # Message type distribution using aggregation
    message_type_pipeline = [
        {"$match": {"created_at": {"$gte": thirty_days_ago}}},
        {"$group": {
            "_id": "$message_type",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    message_types = list(mongo.db.messages.aggregate(message_type_pipeline))
    group_message_types = list(mongo.db.group_messages.aggregate(message_type_pipeline))
    
    # Hourly message distribution
    hourly_pipeline = [
        {"$match": {"created_at": {"$gte": thirty_days_ago}}},
        {"$group": {
            "_id": {"$hour": "$created_at"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    hourly_messages = list(mongo.db.messages.aggregate(hourly_pipeline))
    
    # Get conversation summary data with resolved usernames
    try:
        # Use aggregation pipeline to get conversations with usernames
        conversation_pipeline = [
            {"$match": {"is_deleted": False}},
            {"$group": {
                "_id": "$room_id",
                "participant_1": {"$first": "$sender_id"},
                "participant_2": {"$first": "$recipient_id"},
                "total_messages": {"$sum": 1},
                "last_message_time": {"$max": "$created_at"},
                "unread_count": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", "sent"]}, 1, 0]
                    }
                }
            }},
            {"$lookup": {
                "from": "users",
                "localField": "participant_1",
                "foreignField": "_id",
                "as": "user1_info"
            }},
            {"$lookup": {
                "from": "users",
                "localField": "participant_2", 
                "foreignField": "_id",
                "as": "user2_info"
            }},
            {"$addFields": {
                "conversation_name": {
                    "$cond": {
                        "if": {"$and": [
                            {"$gt": [{"$size": "$user1_info"}, 0]},
                            {"$gt": [{"$size": "$user2_info"}, 0]}
                        ]},
                        "then": {
                            "$concat": [
                                {"$arrayElemAt": ["$user1_info.username", 0]},
                                " ↔ ",
                                {"$arrayElemAt": ["$user2_info.username", 0]}
                            ]
                        },
                        "else": "Unknown Conversation"
                    }
                }
            }},
            {"$sort": {"total_messages": -1}},
            {"$limit": 5}
        ]
        
        conversation_result = list(mongo.db.messages.aggregate(conversation_pipeline))
        active_conversations = [
            {
                "room_id": conv.get("conversation_name", conv.get("_id")),
                "total_messages": conv.get("total_messages", 0),
                "last_message_time": conv.get("last_message_time"),
                "unread_count": conv.get("unread_count", 0)
            }
            for conv in conversation_result
        ]
    except Exception as e:
        print(f"Error getting conversation data: {e}")
        active_conversations = []
    
    response_data = {
        "total_messages": total_messages,
        "total_group_messages": total_group_messages,
        "recent_messages": recent_messages,
        "recent_group_messages": recent_group_messages,
        "daily_messages": serialize_datetime(daily_messages),
        "daily_group_messages": serialize_datetime(daily_group_messages),
        "message_type_distribution": message_types,
        "group_message_type_distribution": group_message_types,
        "hourly_message_distribution": hourly_messages,
        "most_active_conversations": serialize_datetime(active_conversations)
    }
    
    return jsonify(response_data)

@bp.route('/analytics/group_stats', methods=['GET'])
def group_stats():
    """Get enhanced group statistics using database views"""
    total_groups = mongo.db.groups.count_documents({})
    active_groups = mongo.db.groups.count_documents({"is_active": True})
    
    # Get groups created in the last 30 days
    thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
    new_groups = mongo.db.groups.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Enhanced group analytics using aggregation pipeline
    pipeline = [
        {"$match": {"is_active": True}},
        {"$project": {
            "_id": 1,
            "member_count": {"$size": "$members"},
            "admin_count": {"$size": "$admins"}
        }},
        {"$group": {
            "_id": None,
            "avg_members": {"$avg": "$member_count"},
            "max_members": {"$max": "$member_count"},
            "min_members": {"$min": "$member_count"},
            "avg_admins": {"$avg": "$admin_count"}
        }}
    ]
    stats_result = list(mongo.db.groups.aggregate(pipeline))
    group_stats_data = stats_result[0] if stats_result else {}
    
    # Get detailed group analytics with corrected messages_per_day calculation
    try:
        # Use aggregation pipeline to calculate correct messages_per_day
        thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
        
        most_active_groups_pipeline = [
            {"$match": {"is_active": True}},
            {"$lookup": {
                "from": "group_messages",
                "localField": "_id",
                "foreignField": "group_id",
                "as": "messages"
            }},
            {"$addFields": {
                "member_count": {"$size": "$members"},
                "total_messages": {"$size": "$messages"},
                "recent_messages": {
                    "$size": {
                        "$filter": {
                            "input": "$messages",
                            "cond": {"$gte": ["$$this.created_at", thirty_days_ago]}
                        }
                    }
                }
            }},
            {"$addFields": {
                "messages_per_day": {"$round": [{"$divide": ["$recent_messages", 30]}, 2]},
                "messages_per_member": {
                    "$cond": {
                        "if": {"$gt": ["$member_count", 0]},
                        "then": {"$round": [{"$divide": ["$total_messages", "$member_count"]}, 2]},
                        "else": 0
                    }
                }
            }},
            {"$match": {"total_messages": {"$gt": 0}}},
            {"$sort": {"total_messages": -1}},
            {"$limit": 10},
            {"$project": {
                "name": 1,
                "member_count": 1,
                "total_messages": 1,
                "messages_per_day": 1,
                "messages_per_member": 1
            }}
        ]
        
        top_groups_result = list(mongo.db.groups.aggregate(most_active_groups_pipeline))
        top_groups = [
            {
                "name": group.get("name", "Unknown"),
                "member_count": group.get("member_count", 0),
                "total_messages": group.get("total_messages", 0),
                "messages_per_day": group.get("messages_per_day", 0),
                "messages_per_member": group.get("messages_per_member", 0)
            }
            for group in top_groups_result
        ]
    except Exception as e:
        print(f"Error getting group analytics data: {e}")
        top_groups = []
    
    # Group size distribution
    size_distribution_pipeline = [
        {"$match": {"is_active": True}},
        {"$project": {
            "size_category": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": [{"$size": "$members"}, 5]}, "then": "Small (1-5)"},
                        {"case": {"$lte": [{"$size": "$members"}, 15]}, "then": "Medium (6-15)"},
                        {"case": {"$lte": [{"$size": "$members"}, 50]}, "then": "Large (16-50)"},
                        {"case": {"$gt": [{"$size": "$members"}, 50]}, "then": "Very Large (50+)"}
                    ],
                    "default": "Unknown"
                }
            }
        }},
        {"$group": {
            "_id": "$size_category",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    size_distribution = list(mongo.db.groups.aggregate(size_distribution_pipeline))
    
    return jsonify({
        "total_groups": total_groups,
        "active_groups": active_groups,
        "new_groups_last_30_days": new_groups,
        "avg_members_per_group": group_stats_data.get("avg_members", 0),
        "max_members_in_group": group_stats_data.get("max_members", 0),
        "min_members_in_group": group_stats_data.get("min_members", 0),
        "avg_admins_per_group": group_stats_data.get("avg_admins", 0),
        "group_size_distribution": size_distribution,
        "most_active_groups": top_groups
    })

@bp.route('/analytics/file_stats', methods=['GET'])
def file_stats():
    """Get enhanced file statistics using database views"""
    total_files = mongo.db.files.count_documents({})
    
    # Get total storage used using aggregation
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {
            "_id": None,
            "total_size": {"$sum": "$file_size"},
            "avg_size": {"$avg": "$file_size"},
            "max_size": {"$max": "$file_size"},
            "total_downloads": {"$sum": "$download_count"}
        }}
    ]
    size_result = list(mongo.db.files.aggregate(pipeline))
    file_stats_data = size_result[0] if size_result else {}
    
    # Enhanced file type distribution with size information
    type_distribution_pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {
            "_id": "$file_type",
            "count": {"$sum": 1},
            "total_size": {"$sum": "$file_size"},
            "avg_size": {"$avg": "$file_size"},
            "total_downloads": {"$sum": "$download_count"}
        }},
        {"$sort": {"count": -1}}
    ]
    file_types = list(mongo.db.files.aggregate(type_distribution_pipeline))
    
    # Get file usage analytics from view
    try:
        file_usage_data = DatabaseViews.get_view_data("file_usage_summary", limit=10)
        top_uploaders = [
            {
                "username": user.get("username", "Unknown"),
                "total_files": user.get("total_files", 0),
                "total_size_mb": user.get("total_size_mb", 0),
                "total_downloads": user.get("total_downloads", 0),
                "avg_downloads_per_file": user.get("avg_downloads_per_file", 0)
            }
            for user in file_usage_data
        ]
    except Exception as e:
        print(f"Error getting file usage data: {e}")
        top_uploaders = []
    
    # Files uploaded over time (last 30 days)
    thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
    upload_timeline_pipeline = [
        {"$match": {"created_at": {"$gte": thirty_days_ago}, "is_deleted": False}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1},
            "size": {"$sum": "$file_size"}
        }},
        {"$sort": {"_id": 1}}
    ]
    upload_timeline = list(mongo.db.files.aggregate(upload_timeline_pipeline))
    
    return jsonify({
        "total_files": total_files,
        "total_storage_bytes": file_stats_data.get("total_size", 0),
        "total_storage_mb": round(file_stats_data.get("total_size", 0) / 1048576, 2),
        "avg_file_size_bytes": file_stats_data.get("avg_size", 0),
        "max_file_size_bytes": file_stats_data.get("max_size", 0),
        "total_downloads": file_stats_data.get("total_downloads", 0),
        "file_type_distribution": file_types,
        "top_uploaders": top_uploaders,
        "upload_timeline": upload_timeline
    })

@bp.route('/analytics/presence_stats', methods=['GET'])
def presence_stats():
    """Get enhanced presence statistics using aggregation pipelines"""
    total_online = mongo.db.presence.count_documents({"status": "online"})
    
    # Enhanced peak online times (by hour) for the last 7 days
    week_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=7)
    hourly_presence_pipeline = [
        {"$match": {"last_updated": {"$gte": week_ago}}},
        {"$project": {
            "hour": {"$hour": "$last_updated"},
            "day_of_week": {"$dayOfWeek": "$last_updated"},
            "status": 1
        }},
        {"$match": {"status": "online"}},
        {"$group": {
            "_id": {
                "hour": "$hour",
                "day": "$day_of_week"
            },
            "count": {"$sum": 1}
        }},
        {"$group": {
            "_id": "$_id.hour",
            "avg_count": {"$avg": "$count"},
            "max_count": {"$max": "$count"}
        }},
        {"$sort": {"_id": 1}}
    ]
    hourly_presence = list(mongo.db.presence.aggregate(hourly_presence_pipeline))
    
    # Daily presence patterns
    daily_presence_pipeline = [
        {"$match": {"last_updated": {"$gte": week_ago}}},
        {"$project": {
            "day_of_week": {"$dayOfWeek": "$last_updated"},
            "status": 1
        }},
        {"$match": {"status": "online"}},
        {"$group": {
            "_id": "$day_of_week",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_presence = list(mongo.db.presence.aggregate(daily_presence_pipeline))
    
    # User activity patterns
    user_activity_pipeline = [
        {"$match": {"last_updated": {"$gte": week_ago}}},
        {"$group": {
            "_id": "$user_id",
            "online_sessions": {"$sum": {"$cond": [{"$eq": ["$status", "online"]}, 1, 0]}},
            "last_seen": {"$max": "$last_updated"}
        }},
        {"$group": {
            "_id": None,
            "avg_sessions_per_user": {"$avg": "$online_sessions"},
            "active_users_count": {"$sum": 1}
        }}
    ]
    activity_result = list(mongo.db.presence.aggregate(user_activity_pipeline))
    activity_stats = activity_result[0] if activity_result else {}
    
    return jsonify({
        "currently_online": total_online,
        "hourly_presence_patterns": hourly_presence,
        "daily_presence_patterns": daily_presence,
        "avg_sessions_per_user": activity_stats.get("avg_sessions_per_user", 0),
        "active_users_last_week": activity_stats.get("active_users_count", 0)
    })

@bp.route('/analytics/call_stats', methods=['GET'])
def call_stats():
    """Get comprehensive call statistics for all users"""
    try:
        # Overall call statistics
        total_calls = mongo.db.calls.count_documents({})
        
        # Call status distribution
        status_pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        status_distribution = list(mongo.db.calls.aggregate(status_pipeline))
        
        # Call type distribution
        type_pipeline = [
            {"$group": {
                "_id": "$call_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        type_distribution = list(mongo.db.calls.aggregate(type_pipeline))
        
        # Daily call volume (last 30 days)
        thirty_days_ago = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=30)
        daily_calls_pipeline = [
            {"$match": {"start_time": {"$gte": thirty_days_ago}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$start_time"}},
                "total_calls": {"$sum": 1},
                "answered_calls": {"$sum": {"$cond": [{"$and": [{"$ne": ["$status", "declined"]}, {"$ne": ["$status", "missed"]}]}, 1, 0]}},
                "missed_calls": {"$sum": {"$cond": [{"$eq": ["$status", "missed"]}, 1, 0]}},
                "declined_calls": {"$sum": {"$cond": [{"$eq": ["$status", "declined"]}, 1, 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        daily_calls = list(mongo.db.calls.aggregate(daily_calls_pipeline))
        
        # Hourly call distribution
        hourly_calls_pipeline = [
            {"$match": {"start_time": {"$gte": thirty_days_ago}}},
            {"$group": {
                "_id": {"$hour": "$start_time"},
                "count": {"$sum": 1},
                "answered_rate": {"$avg": {"$cond": [{"$and": [{"$ne": ["$status", "declined"]}, {"$ne": ["$status", "missed"]}]}, 1, 0]}}
            }},
            {"$sort": {"_id": 1}}
        ]
        hourly_calls = list(mongo.db.calls.aggregate(hourly_calls_pipeline))
        

        
        # Top callers
        top_callers_pipeline = [
            {"$group": {
                "_id": "$caller_id",
                "total_calls": {"$sum": 1},
                "answered_calls": {"$sum": {"$cond": [{"$and": [{"$ne": ["$status", "declined"]}, {"$ne": ["$status", "missed"]}]}, 1, 0]}}
            }},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user_info"
            }},
            {"$unwind": "$user_info"},
            {"$project": {
                "username": "$user_info.username",
                "total_calls": 1,
                "answered_calls": 1,
                "answer_rate": {"$divide": ["$answered_calls", "$total_calls"]}
            }},
            {"$sort": {"total_calls": -1}},
            {"$limit": 10}
        ]
        top_callers = list(mongo.db.calls.aggregate(top_callers_pipeline))
        
        # Recent calls
        recent_calls = mongo.db.calls.count_documents({"start_time": {"$gte": thirty_days_ago}})
        
        # Answer rate calculation - anything not declined or missed is considered answered
        answered_calls = sum(item["count"] for item in status_distribution if item["_id"] not in ["declined", "missed"])
        answer_rate = round((answered_calls / max(total_calls, 1)) * 100, 1) if total_calls > 0 else 0
        
        response_data = {
            "total_calls": total_calls,
            "recent_calls_30d": recent_calls,
            "status_distribution": status_distribution,
            "type_distribution": type_distribution,
            "daily_call_volume": serialize_datetime(daily_calls),
            "hourly_call_distribution": hourly_calls,
            "top_callers": top_callers,
            "answer_rate": answer_rate
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error getting call statistics: {e}")
        return jsonify({
            "total_calls": 0,
            "recent_calls_30d": 0,
            "status_distribution": [],
            "type_distribution": [],
            "daily_call_volume": [],
            "hourly_call_distribution": [],
            "top_callers": [],
            "answer_rate": 0
        })



@bp.route('/analytics/views/create', methods=['POST'])
def create_analytics_views():
    """Create or refresh all database views"""
    try:
        results = DatabaseViews.create_all_views()
        return jsonify({
            "success": True,
            "message": "Database views created/refreshed successfully",
            "results": results
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error creating views: {str(e)}"
        }), 500

@bp.route('/analytics/views/<view_name>', methods=['GET'])
def get_view_data(view_name):
    """Get data from a specific analytics view"""
    try:
        limit = request.args.get('limit', 20, type=int)
        skip = request.args.get('skip', 0, type=int)
        
        data = DatabaseViews.get_view_data(view_name, limit=limit, skip=skip)
        
        return jsonify({
            "success": True,
            "view_name": view_name,
            "data": data,
            "count": len(data)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error getting view data: {str(e)}"
        }), 500




