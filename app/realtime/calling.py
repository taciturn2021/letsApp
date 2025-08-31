from flask_socketio import emit, join_room, leave_room
from flask import request
from app import mongo
from app.models.call import Call
from app.models.user import User
from flask_jwt_extended import decode_token
from bson import ObjectId
import datetime
from datetime import timezone

# Store active call sessions in memory for quick access
active_calls = {}  # call_id -> {caller_id, callee_id, status, room_name}

def get_user_from_token():
    """Extract user from JWT token in socket session"""
    try:
        token = request.args.get('token')
        if not token:
            return None
        
        payload = decode_token(token)
        if not payload:
            return None
            
        user_id = payload.get('sub')  # Use 'sub' as that's the standard JWT claim
        if not user_id:
            return None
            
        user = User.get_by_id(user_id)
        return user
    except Exception as e:
        print(f"Error getting user from token: {e}")
        return None

def register_handlers(socketio):
    """Register all Socket.IO event handlers for calling functionality"""
    
    @socketio.on('call_initiate')
    def handle_call_initiate(data):
        """Handle call initiation"""
        print(f"===== WEBSOCKET: Call Initiate Event Received =====")
        print(f"Data received: {data}")
        
        try:
            user = get_user_from_token()
            print(f"User from token: {user}")
            
            if not user:
                print("ERROR: Authentication failed - no user found")
                emit('call_error', {'message': 'Authentication required'})
                return
            
            callee_id = data.get('callee_id')
            call_type = data.get('call_type', 'voice')
            
            print(f"Caller ID: {str(user['_id'])}, Callee ID: {callee_id}, Call Type: {call_type}")
            
            if not callee_id:
                print("ERROR: No callee ID provided")
                emit('call_error', {'message': 'Callee ID is required'})
                return
            
            # Check if callee exists and is online
            callee = User.get_by_id(callee_id)
            if not callee:
                print(f"ERROR: Callee {callee_id} not found")
                emit('call_error', {'message': 'User not found'})
                return
            
            print(f"Callee found: {callee.get('username')}")
            
            # Check if either user is already in a call
            caller_id = str(user['_id'])
            if is_user_in_call(caller_id) or is_user_in_call(callee_id):
                print(f"ERROR: User already in call - Caller: {is_user_in_call(caller_id)}, Callee: {is_user_in_call(callee_id)}")
                emit('call_error', {'message': 'User is already in a call'})
                return
            
            # Create call session in database
            call_session = Call.create_call_session(caller_id, callee_id, call_type)
            call_id = str(call_session['_id'])
            
            print(f"Call session created with ID: {call_id}")
            
            # Create call room name
            call_room = f"call_{call_id}"
            
            # Store in active calls
            active_calls[call_id] = {
                'caller_id': caller_id,
                'callee_id': callee_id,
                'status': 'initiated',
                'room_name': call_room,
                'call_type': call_type
            }
            
            print(f"Active calls now: {list(active_calls.keys())}")
            
            # Join caller to call room
            join_room(call_room)
            print(f"Caller joined room: {call_room}")
            
            # Update call status to ringing
            Call.update_call_status(call_id, 'ringing')
            active_calls[call_id]['status'] = 'ringing'
            
            # Notify callee about incoming call
            callee_room = f"user_{callee_id}"
            print(f"Sending incoming_call to room: {callee_room}")
            
            # Check if callee is connected
            from app.realtime.events import connected_users
            callee_connected = callee_id in connected_users
            print(f"DEBUG: Callee {callee_id} connected: {callee_connected}")
            if callee_connected:
                print(f"DEBUG: Callee session ID: {connected_users[callee_id]}")
            else:
                print(f"DEBUG: Callee {callee_id} is not in connected_users: {list(connected_users.keys())}")
            
            emit('incoming_call', {
                'call_id': call_id,
                'caller': {
                    'id': caller_id,
                    'username': user.get('username'),
                    'full_name': user.get('full_name'),
                    'profile_picture': user.get('profile_picture')
                },
                'call_type': call_type
            }, room=callee_room)
            
            print(f"DEBUG: incoming_call event emitted to room {callee_room}")
            
            # Confirm call initiation to caller
            emit('call_initiated', {
                'call_id': call_id,
                'status': 'ringing',
                'callee': {
                    'id': callee_id,
                    'username': callee.get('username'),
                    'full_name': callee.get('full_name'),
                    'profile_picture': callee.get('profile_picture')
                }
            })
            
            print(f"Call initiated: {caller_id} -> {callee_id} (Call ID: {call_id})")
            print("===== Call Initiate Event Completed Successfully =====")
            
        except Exception as e:
            print(f"Error initiating call: {e}")
            import traceback
            traceback.print_exc()
            emit('call_error', {'message': 'Failed to initiate call'})

    @socketio.on('call_answer')
    def handle_call_answer(data):
        """Handle call answer"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            if not call_id or call_id not in active_calls:
                emit('call_error', {'message': 'Invalid call ID'})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is the callee
            if user_id != call_info['callee_id']:
                emit('call_error', {'message': 'Unauthorized to answer this call'})
                return
            
            # Prevent duplicate answer handling
            if call_info['status'] in ['answered', 'connected']:
                print(f"Call {call_id} already answered, ignoring duplicate answer")
                # Still send confirmation to avoid frontend hanging
                emit('call_answer_confirmed', {'call_id': call_id})
                return
            
            # Update call status
            Call.update_call_status(call_id, 'answered')
            active_calls[call_id]['status'] = 'answered'
            
            # Join callee to call room
            call_room = call_info['room_name']
            join_room(call_room)
            
            # Notify caller that call was answered
            emit('call_answered', {
                'call_id': call_id,
                'callee': {
                    'id': user_id,
                    'username': user.get('username'),
                    'full_name': user.get('full_name')
                }
            }, room=f"user_{call_info['caller_id']}")
            
            # Confirm to callee
            emit('call_answer_confirmed', {'call_id': call_id})
            
            print(f"Call answered: {call_id}")
            
        except Exception as e:
            print(f"Error answering call: {e}")
            emit('call_error', {'message': 'Failed to answer call'})

    @socketio.on('call_decline')
    def handle_call_decline(data):
        """Handle call decline"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            if not call_id:
                emit('call_error', {'message': 'Call ID is required'})
                return
                
            if call_id not in active_calls:
                emit('call_error', {'message': 'Invalid call ID'})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is the callee
            if user_id != call_info['callee_id']:
                emit('call_error', {'message': 'Unauthorized to decline this call'})
                return
            
            # Update call status in database
            try:
                Call.update_call_status(call_id, 'declined')
            except Exception as db_error:
                print(f"Error updating call status in database: {db_error}")
            
            # Notify caller that call was declined
            emit('call_declined', {'call_id': call_id}, room=f"user_{call_info['caller_id']}")
            
            # Confirm to callee
            emit('call_decline_confirmed', {'call_id': call_id})
            
            # Clean up call session
            cleanup_call_session(call_id)
            
            print(f"Call declined: {call_id}")
            
        except Exception as e:
            print(f"Error declining call: {e}")
            emit('call_error', {'message': 'Failed to decline call'})

    @socketio.on('call_end')
    def handle_call_end(data):
        """Handle call end"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            if not call_id:
                emit('call_error', {'message': 'Call ID is required'})
                return
            
            # Check if call exists in active calls
            if call_id not in active_calls:
                # Call might have already ended, just confirm
                emit('call_end_confirmed', {'call_id': call_id})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is part of this call
            if user_id not in [call_info['caller_id'], call_info['callee_id']]:
                emit('call_error', {'message': 'Unauthorized to end this call'})
                return
            
            # Update call status and end time in database
            try:
                Call.end_call(call_id)
            except Exception as db_error:
                print(f"Error updating call in database: {db_error}")
                # Continue with cleanup even if database update fails
            
            # Notify other participant that call ended
            other_user_id = call_info['callee_id'] if user_id == call_info['caller_id'] else call_info['caller_id']
            emit('call_ended', {'call_id': call_id}, room=f"user_{other_user_id}")
            
            # Confirm to the user who ended the call
            emit('call_end_confirmed', {'call_id': call_id})
            
            # Clean up call session
            cleanup_call_session(call_id)
            
            print(f"Call ended: {call_id} by user {user_id}")
            
        except Exception as e:
            print(f"Error ending call: {e}")
            emit('call_error', {'message': 'Failed to end call'})

    @socketio.on('webrtc_offer')
    def handle_webrtc_offer(data):
        """Handle WebRTC offer for call establishment"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            offer = data.get('offer')
            
            if not call_id or call_id not in active_calls:
                emit('call_error', {'message': 'Invalid call ID'})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is the caller
            if user_id != call_info['caller_id']:
                emit('call_error', {'message': 'Only caller can send offer'})
                return
            
            # Forward offer to callee
            emit('webrtc_offer', {
                'call_id': call_id,
                'offer': offer
            }, room=f"user_{call_info['callee_id']}")
            
            print(f"WebRTC offer forwarded for call: {call_id}")
            
        except Exception as e:
            print(f"Error handling WebRTC offer: {e}")
            emit('call_error', {'message': 'Failed to process WebRTC offer'})

    @socketio.on('webrtc_answer')
    def handle_webrtc_answer(data):
        """Handle WebRTC answer for call establishment"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            answer = data.get('answer')
            
            if not call_id or call_id not in active_calls:
                emit('call_error', {'message': 'Invalid call ID'})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is the callee
            if user_id != call_info['callee_id']:
                emit('call_error', {'message': 'Only callee can send answer'})
                return
            
            # Update call status to connected
            Call.update_call_status(call_id, 'connected')
            active_calls[call_id]['status'] = 'connected'
            
            # Forward answer to caller
            emit('webrtc_answer', {
                'call_id': call_id,
                'answer': answer
            }, room=f"user_{call_info['caller_id']}")
            
            print(f"WebRTC answer forwarded for call: {call_id}")
            
        except Exception as e:
            print(f"Error handling WebRTC answer: {e}")
            emit('call_error', {'message': 'Failed to process WebRTC answer'})

    @socketio.on('webrtc_ice_candidate')
    def handle_ice_candidate(data):
        """Handle ICE candidate exchange for WebRTC"""
        try:
            user = get_user_from_token()
            if not user:
                emit('call_error', {'message': 'Authentication required'})
                return
            
            call_id = data.get('call_id')
            candidate = data.get('candidate')
            
            if not call_id or call_id not in active_calls:
                emit('call_error', {'message': 'Invalid call ID'})
                return
            
            call_info = active_calls[call_id]
            user_id = str(user['_id'])
            
            # Verify user is part of this call
            if user_id not in [call_info['caller_id'], call_info['callee_id']]:
                emit('call_error', {'message': 'Unauthorized to send ICE candidate'})
                return
            
            # Forward ICE candidate to the other participant
            other_user_id = call_info['callee_id'] if user_id == call_info['caller_id'] else call_info['caller_id']
            emit('webrtc_ice_candidate', {
                'call_id': call_id,
                'candidate': candidate
            }, room=f"user_{other_user_id}")
            
            print(f"ICE candidate forwarded for call: {call_id}")
            
        except Exception as e:
            print(f"Error handling ICE candidate: {e}")
            emit('call_error', {'message': 'Failed to process ICE candidate'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle user disconnection - clean up any active calls"""
        try:
            user = get_user_from_token()
            if user:
                user_id = str(user['_id'])
                cleanup_user_calls(user_id)
                print(f"Cleaned up calls for disconnected user: {user_id}")
        except Exception as e:
            print(f"Error cleaning up calls on disconnect: {e}")

def is_user_in_call(user_id):
    """Check if a user is currently in any active call"""
    try:
        for call_info in active_calls.values():
            if user_id in [call_info['caller_id'], call_info['callee_id']]:
                return True
        return False
    except Exception as e:
        print(f"Error checking if user {user_id} is in call: {e}")
        return False

def cleanup_call_session(call_id):
    """Clean up call session from memory and update database"""
    try:
        if call_id in active_calls:
            call_info = active_calls[call_id]
            print(f"Cleaning up call session: {call_id} (caller: {call_info['caller_id']}, callee: {call_info['callee_id']})")
            del active_calls[call_id]
        else:
            print(f"Call session {call_id} not found in active calls")
        
        print(f"Active calls remaining: {len(active_calls)}")
    except Exception as e:
        print(f"Error cleaning up call session {call_id}: {e}")

def cleanup_user_calls(user_id):
    """Clean up all calls for a specific user (when they disconnect)"""
    try:
        calls_to_cleanup = []
        for call_id, call_info in active_calls.items():
            if user_id in [call_info['caller_id'], call_info['callee_id']]:
                calls_to_cleanup.append(call_id)
        
        for call_id in calls_to_cleanup:
            try:
                # End the call in database
                Call.end_call(call_id)
                
                # Get call info before cleanup
                call_info = active_calls.get(call_id)
                if call_info:
                    # Notify other participant
                    other_user_id = call_info['callee_id'] if user_id == call_info['caller_id'] else call_info['caller_id']
                    emit('call_ended', {
                        'call_id': call_id,
                        'reason': 'participant_disconnected'
                    }, room=f"user_{other_user_id}")
                
                # Clean up from memory
                cleanup_call_session(call_id)
                
            except Exception as call_error:
                print(f"Error cleaning up individual call {call_id}: {call_error}")
                # Still try to remove from active calls
                if call_id in active_calls:
                    del active_calls[call_id]
            
        print(f"Cleaned up {len(calls_to_cleanup)} calls for user {user_id}")
        
    except Exception as e:
        print(f"Error cleaning up calls for user {user_id}: {e}") 