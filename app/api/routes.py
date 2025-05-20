from flask import jsonify, request, Blueprint, render_template
from app.api import bp
from app.models import User, Message, Group, GroupMessage, Contact, File, Presence
from app.models.presence import Presence
from bson import ObjectId
import datetime


bp = Blueprint('load', __name__)

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
        
        # Add presence status
        user_id = str(user.get('_id'))
        user['status'] = Presence.get_status(user_id)
        
    print(f"Returning {len(users)} users with presence status")
    return jsonify({"users": users})

# Analytics Endpoints
from app import mongo

@bp.route('/analytics/user_stats', methods=['GET'])
def user_stats():
    """Get user statistics for analytics"""
    total_users = mongo.db.users.count_documents({})
    active_users = mongo.db.users.count_documents({"is_active": True})
    
    # Get users registered in the last 30 days
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    new_users = mongo.db.users.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Get users active in the last 24 hours
    day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    active_today = mongo.db.users.count_documents({"last_seen": {"$gte": day_ago}})
    
    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "new_users_last_30_days": new_users,
        "active_users_last_24h": active_today
    })

@bp.route('/analytics/message_stats', methods=['GET'])
def message_stats():
    """Get message statistics for analytics"""
    total_messages = mongo.db.messages.count_documents({})
    total_group_messages = mongo.db.group_messages.count_documents({})
    
    # Get messages sent in the last 30 days
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    recent_messages = mongo.db.messages.count_documents({"created_at": {"$gte": thirty_days_ago}})
    recent_group_messages = mongo.db.group_messages.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Get daily message counts for the last 30 days
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
    
    return jsonify({
        "total_messages": total_messages,
        "total_group_messages": total_group_messages,
        "recent_messages": recent_messages,
        "recent_group_messages": recent_group_messages,
        "daily_messages": daily_messages,
        "daily_group_messages": daily_group_messages
    })

@bp.route('/analytics/group_stats', methods=['GET'])
def group_stats():
    """Get group statistics for analytics"""
    total_groups = mongo.db.groups.count_documents({})
    active_groups = mongo.db.groups.count_documents({"is_active": True})
    
    # Get groups created in the last 30 days
    thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    new_groups = mongo.db.groups.count_documents({"created_at": {"$gte": thirty_days_ago}})
    
    # Get average members per group
    pipeline = [
        {"$match": {"is_active": True}},
        {"$project": {
            "_id": 1,
            "member_count": {"$size": "$members"}
        }},
        {"$group": {
            "_id": None,
            "avg_members": {"$avg": "$member_count"}
        }}
    ]
    avg_result = list(mongo.db.groups.aggregate(pipeline))
    avg_members = avg_result[0]["avg_members"] if avg_result else 0
    
    return jsonify({
        "total_groups": total_groups,
        "active_groups": active_groups,
        "new_groups_last_30_days": new_groups,
        "avg_members_per_group": avg_members
    })

@bp.route('/analytics/file_stats', methods=['GET'])
def file_stats():
    """Get file statistics for analytics"""
    total_files = mongo.db.files.count_documents({})
    
    # Get total storage used
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {
            "_id": None,
            "total_size": {"$sum": "$file_size"}
        }}
    ]
    size_result = list(mongo.db.files.aggregate(pipeline))
    total_size = size_result[0]["total_size"] if size_result else 0
    
    # Get file type distribution
    pipeline = [
        {"$match": {"is_deleted": False}},
        {"$group": {
            "_id": "$file_type",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]
    file_types = list(mongo.db.files.aggregate(pipeline))
    
    return jsonify({
        "total_files": total_files,
        "total_storage_bytes": total_size,
        "file_type_distribution": file_types
    })

@bp.route('/analytics/presence_stats', methods=['GET'])
def presence_stats():
    """Get presence statistics for analytics"""
    total_online = mongo.db.presence.count_documents({"status": "online"})
    
    # Get peak online times (by hour)
    day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    pipeline = [
        {"$match": {"last_updated": {"$gte": day_ago}}},
        {"$project": {
            "hour": {"$hour": "$last_updated"},
            "status": 1
        }},
        {"$match": {"status": "online"}},
        {"$group": {
            "_id": "$hour",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    hourly_presence = list(mongo.db.presence.aggregate(pipeline))
    
    return jsonify({
        "currently_online": total_online,
        "hourly_presence": hourly_presence
    })

@bp.route('/analytics', methods=['GET'])
def analytics_page():
    """Render the analytics page"""
    return render_template('analytics.html')


