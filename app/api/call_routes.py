from flask import jsonify, request, Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.call import Call
from app.models.user import User
from bson import ObjectId
import datetime

# Create blueprint for call routes
call_bp = Blueprint('calls', __name__, url_prefix='/api/calls')

@call_bp.route('/history', methods=['GET'])
@jwt_required()
def get_call_history():
    """Get call history for the current user"""
    try:
        current_user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        skip = (page - 1) * limit
        
        call_history = Call.get_user_call_history(current_user_id, limit=limit, skip=skip)
        
        # Format the response
        formatted_history = []
        for call in call_history:
            # Determine the other participant
            if call['is_incoming']:
                other_participant = call['caller']
                call_direction = 'incoming'
            else:
                other_participant = call['callee']
                call_direction = 'outgoing'
            
            formatted_call = {
                'id': str(call['_id']),
                'call_type': call['call_type'],
                'status': call['status'],
                'direction': call_direction,
                'participant': {
                    'id': str(other_participant['id']),
                    'username': other_participant['username'],
                    'full_name': other_participant.get('full_name'),
                    'profile_picture': other_participant.get('profile_picture')
                },
                'start_time': call['start_time'].isoformat() if call['start_time'] else None,
                'answer_time': call['answer_time'].isoformat() if call.get('answer_time') else None,
                'end_time': call['end_time'].isoformat() if call.get('end_time') else None,
                'duration': call.get('duration'),
                'quality_metrics': call.get('quality_metrics', {})
            }
            formatted_history.append(formatted_call)
        
        return jsonify({
            'success': True,
            'data': {
                'calls': formatted_history,
                'page': page,
                'limit': limit,
                'has_more': len(formatted_history) == limit
            }
        })
        
    except Exception as e:
        print(f"Error getting call history: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve call history'
        }), 500

@call_bp.route('/statistics', methods=['GET'])
@jwt_required()
def get_call_statistics():
    """Get call statistics for the current user"""
    try:
        current_user_id = get_jwt_identity()
        stats = Call.get_call_statistics(current_user_id)
        
        # Format duration for better readability
        total_duration_formatted = format_duration(stats.get('total_duration', 0))
        avg_duration_formatted = format_duration(stats.get('avg_duration', 0))
        
        formatted_stats = {
            'total_calls': stats.get('total_calls', 0),
            'answered_calls': stats.get('answered_calls', 0),
            'missed_calls': stats.get('missed_calls', 0),
            'declined_calls': stats.get('declined_calls', 0),
            'incoming_calls': stats.get('incoming_calls', 0),
            'outgoing_calls': stats.get('outgoing_calls', 0),
            'total_duration': stats.get('total_duration', 0),
            'total_duration_formatted': total_duration_formatted,
            'avg_duration': stats.get('avg_duration', 0),
            'avg_duration_formatted': avg_duration_formatted,
            'answer_rate': round((stats.get('answered_calls', 0) / max(stats.get('total_calls', 1), 1)) * 100, 1)
        }
        
        return jsonify({
            'success': True,
            'data': formatted_stats
        })
        
    except Exception as e:
        print(f"Error getting call statistics: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve call statistics'
        }), 500

@call_bp.route('/missed', methods=['GET'])
@jwt_required()
def get_missed_calls():
    """Get missed calls for the current user"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get recent missed calls (last 30 days)
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        
        pipeline = [
            {
                "$match": {
                    "callee_id": ObjectId(current_user_id),
                    "status": "missed",
                    "start_time": {"$gte": thirty_days_ago}
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
                "$unwind": "$caller_info"
            },
            {
                "$project": {
                    "call_type": 1,
                    "start_time": 1,
                    "caller": {
                        "id": "$caller_info._id",
                        "username": "$caller_info.username",
                        "full_name": "$caller_info.full_name",
                        "profile_picture": "$caller_info.profile_picture"
                    }
                }
            },
            {
                "$sort": {"start_time": -1}
            },
            {
                "$limit": 50
            }
        ]
        
        from app import mongo
        missed_calls = list(mongo.db.calls.aggregate(pipeline))
        
        # Format the response
        formatted_calls = []
        for call in missed_calls:
            formatted_call = {
                'id': str(call['_id']),
                'call_type': call['call_type'],
                'start_time': call['start_time'].isoformat(),
                'caller': {
                    'id': str(call['caller']['id']),
                    'username': call['caller']['username'],
                    'full_name': call['caller'].get('full_name'),
                    'profile_picture': call['caller'].get('profile_picture')
                }
            }
            formatted_calls.append(formatted_call)
        
        return jsonify({
            'success': True,
            'data': {
                'missed_calls': formatted_calls,
                'count': len(formatted_calls)
            }
        })
        
    except Exception as e:
        print(f"Error getting missed calls: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve missed calls'
        }), 500

@call_bp.route('/<call_id>', methods=['GET'])
@jwt_required()
def get_call_details(call_id):
    """Get details of a specific call"""
    try:
        current_user_id = get_jwt_identity()
        call = Call.get_by_id(call_id)
        if not call:
            return jsonify({
                'success': False,
                'message': 'Call not found'
            }), 404
        
        caller_id = str(call['caller_id'])
        callee_id = str(call['callee_id'])
        
        # Verify user is part of this call
        if current_user_id not in [caller_id, callee_id]:
            return jsonify({
                'success': False,
                'message': 'Unauthorized to view this call'
            }), 403
        
        # Get participant information
        from app import mongo
        caller = User.get_by_id(caller_id)
        callee = User.get_by_id(callee_id)
        
        formatted_call = {
            'id': str(call['_id']),
            'call_type': call['call_type'],
            'status': call['status'],
            'start_time': call['start_time'].isoformat() if call['start_time'] else None,
            'answer_time': call['answer_time'].isoformat() if call.get('answer_time') else None,
            'end_time': call['end_time'].isoformat() if call.get('end_time') else None,
            'duration': call.get('duration'),
            'duration_formatted': format_duration(call.get('duration', 0)),
            'quality_metrics': call.get('quality_metrics', {}),
            'caller': {
                'id': caller_id,
                'username': caller.get('username') if caller else 'Unknown',
                'full_name': caller.get('full_name') if caller else None,
                'profile_picture': caller.get('profile_picture') if caller else None
            },
            'callee': {
                'id': callee_id,
                'username': callee.get('username') if callee else 'Unknown',
                'full_name': callee.get('full_name') if callee else None,
                'profile_picture': callee.get('profile_picture') if callee else None
            },
            'is_incoming': current_user_id == callee_id
        }
        
        return jsonify({
            'success': True,
            'data': formatted_call
        })
        
    except Exception as e:
        print(f"Error getting call details: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to retrieve call details'
        }), 500

def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if not seconds or seconds < 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s" 