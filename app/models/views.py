import datetime
from datetime import timezone
from bson import ObjectId
from app import mongo

class DatabaseViews:
    """Database views for enhanced analytics and complex queries."""
    
    @staticmethod
    def create_conversation_summary_view():
        """Create a view that aggregates conversation data for quick access"""
        try:
            # Drop existing view if it exists
            try:
                mongo.db.conversation_summary.drop()
            except:
                pass
            
            pipeline = [
                {
                    "$match": {"is_deleted": False}
                },
                {
                    "$group": {
                        "_id": "$room_id",
                        "participant_1": {"$first": "$sender_id"},
                        "participant_2": {"$first": "$recipient_id"},
                        "all_participants": {"$addToSet": {"$ifNull": ["$sender_id", "$recipient_id"]}},
                        "last_message": {"$last": "$content"},
                        "last_message_time": {"$max": "$created_at"},
                        "last_message_type": {"$last": "$message_type"},
                        "total_messages": {"$sum": 1},
                        "unread_count": {
                            "$sum": {
                                "$cond": [{"$eq": ["$status", "sent"]}, 1, 0]
                            }
                        },
                        "first_message_time": {"$min": "$created_at"}
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "participant_1",
                        "foreignField": "_id",
                        "as": "user1_info"
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "participant_2", 
                        "foreignField": "_id",
                        "as": "user2_info"
                    }
                },
                {
                    "$addFields": {
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
                    }
                },
                {
                    "$sort": {"last_message_time": -1}
                }
            ]
            
            # Create the view
            mongo.db.create_collection("conversation_summary", 
                                      viewOn="messages", 
                                      pipeline=pipeline)
            
            print("Conversation summary view created successfully")
            return True
            
        except Exception as e:
            print(f"Error creating conversation summary view: {e}")
            return False
    
    @staticmethod
    def create_user_activity_view():
        """Create a view for comprehensive user activity analytics"""
        try:
            # Drop existing view if it exists
            try:
                mongo.db.user_activity_summary.drop()
            except:
                pass
            
            pipeline = [
                {
                    "$group": {
                        "_id": "$sender_id",
                        "total_messages": {"$sum": 1},
                        "last_message_time": {"$max": "$created_at"},
                        "first_message_time": {"$min": "$created_at"},
                        "message_types": {
                            "$push": "$message_type"
                        },
                        "avg_message_length": {
                            "$avg": {"$strLenCP": "$content"}
                        },
                        "messages_by_day": {
                            "$push": {
                                "$dateToString": {
                                    "format": "%Y-%m-%d",
                                    "date": "$created_at"
                                }
                            }
                        }
                    }
                },
                {
                    "$addFields": {
                        "text_messages": {
                            "$size": {
                                "$filter": {
                                    "input": "$message_types",
                                    "cond": {"$eq": ["$$this", "text"]}
                                }
                            }
                        },
                        "media_messages": {
                            "$size": {
                                "$filter": {
                                    "input": "$message_types",
                                    "cond": {"$ne": ["$$this", "text"]}
                                }
                            }
                        },
                        "active_days": {
                            "$size": {
                                "$setUnion": ["$messages_by_day", []]
                            }
                        }
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "_id",
                        "foreignField": "_id",
                        "as": "user_info"
                    }
                },
                {
                    "$unwind": "$user_info"
                },
                {
                    "$project": {
                        "user_id": "$_id",
                        "username": "$user_info.username",
                        "email": "$user_info.email",
                        "total_messages": 1,
                        "text_messages": 1,
                        "media_messages": 1,
                        "last_message_time": 1,
                        "first_message_time": 1,
                        "avg_message_length": {"$round": ["$avg_message_length", 2]},
                        "active_days": 1,
                        "messages_per_day": {
                            "$round": [{"$divide": ["$total_messages", "$active_days"]}, 2]
                        }
                    }
                },
                {
                    "$sort": {"total_messages": -1}
                }
            ]
            
            # Create the view
            mongo.db.create_collection("user_activity_summary", 
                                      viewOn="messages", 
                                      pipeline=pipeline)
            
            print("User activity summary view created successfully")
            return True
            
        except Exception as e:
            print(f"Error creating user activity view: {e}")
            return False
    
    @staticmethod
    def create_group_analytics_view():
        """Create a view for group analytics and statistics"""
        try:
            # Drop existing view if it exists
            try:
                mongo.db.group_analytics_summary.drop()
            except:
                pass
            
            pipeline = [
                {
                    "$lookup": {
                        "from": "group_messages",
                        "localField": "_id",
                        "foreignField": "group_id",
                        "as": "messages"
                    }
                },
                {
                    "$addFields": {
                        "member_count": {"$size": "$members"},
                        "admin_count": {"$size": "$admins"},
                        "total_messages": {"$size": "$messages"},
                        "last_message_time": {"$max": "$messages.created_at"},
                        "first_message_time": {"$min": "$messages.created_at"}
                    }
                },
                {
                    "$addFields": {
                        "days_active": {
                            "$cond": {
                                "if": {"$and": ["$first_message_time", "$last_message_time"]},
                                "then": {
                                    "$max": [
                                        1,  # minimum 1 day
                                        {
                                            "$divide": [
                                                {"$subtract": ["$last_message_time", "$first_message_time"]},
                                                86400000  # milliseconds in a day
                                            ]
                                        }
                                    ]
                                },
                                "else": 1
                            }
                        }
                    }
                },
                {
                    "$addFields": {
                        "messages_per_day": {
                            "$cond": {
                                "if": {"$gt": ["$days_active", 0]},
                                "then": {"$divide": ["$total_messages", "$days_active"]},
                                "else": "$total_messages"
                            }
                        },
                        "messages_per_member": {
                            "$cond": {
                                "if": {"$gt": ["$member_count", 0]},
                                "then": {"$divide": ["$total_messages", "$member_count"]},
                                "else": 0
                            }
                        }
                    }
                },
                {
                    "$project": {
                        "group_id": "$_id",
                        "name": 1,
                        "description": 1,
                        "created_at": 1,
                        "member_count": 1,
                        "admin_count": 1,
                        "total_messages": 1,
                        "last_message_time": 1,
                        "first_message_time": 1,
                        "days_active": {"$round": ["$days_active", 1]},
                        "messages_per_day": {"$round": ["$messages_per_day", 2]},
                        "messages_per_member": {"$round": ["$messages_per_member", 2]},
                        "is_active": 1
                    }
                },
                {
                    "$sort": {"total_messages": -1}
                }
            ]
            
            # Create the view
            mongo.db.create_collection("group_analytics_summary", 
                                      viewOn="groups", 
                                      pipeline=pipeline)
            
            print("Group analytics summary view created successfully")
            return True
            
        except Exception as e:
            print(f"Error creating group analytics view: {e}")
            return False
    
    @staticmethod
    def create_file_usage_view():
        """Create a view for file usage analytics"""
        try:
            # Drop existing view if it exists
            try:
                mongo.db.file_usage_summary.drop()
            except:
                pass
            
            pipeline = [
                {
                    "$match": {"is_deleted": False}
                },
                {
                    "$group": {
                        "_id": {
                            "uploader_id": "$uploader_id",
                            "file_type": "$file_type"
                        },
                        "total_files": {"$sum": 1},
                        "total_size": {"$sum": "$file_size"},
                        "total_downloads": {"$sum": "$download_count"},
                        "avg_file_size": {"$avg": "$file_size"},
                        "last_upload": {"$max": "$created_at"},
                        "first_upload": {"$min": "$created_at"}
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "_id.uploader_id",
                        "foreignField": "_id",
                        "as": "user_info"
                    }
                },
                {
                    "$unwind": "$user_info"
                },
                {
                    "$group": {
                        "_id": "$_id.uploader_id",
                        "username": {"$first": "$user_info.username"},
                        "email": {"$first": "$user_info.email"},
                        "file_types": {
                            "$push": {
                                "type": "$_id.file_type",
                                "count": "$total_files",
                                "size": "$total_size",
                                "downloads": "$total_downloads"
                            }
                        },
                        "total_files_all_types": {"$sum": "$total_files"},
                        "total_size_all_types": {"$sum": "$total_size"},
                        "total_downloads_all_types": {"$sum": "$total_downloads"},
                        "last_upload": {"$max": "$last_upload"},
                        "first_upload": {"$min": "$first_upload"}
                    }
                },
                {
                    "$project": {
                        "user_id": "$_id",
                        "username": 1,
                        "email": 1,
                        "file_types": 1,
                        "total_files": "$total_files_all_types",
                        "total_size_mb": {
                            "$round": [{"$divide": ["$total_size_all_types", 1048576]}, 2]
                        },
                        "total_downloads": "$total_downloads_all_types",
                        "avg_downloads_per_file": {
                            "$round": [
                                {"$divide": ["$total_downloads_all_types", "$total_files_all_types"]}, 
                                2
                            ]
                        },
                        "last_upload": 1,
                        "first_upload": 1
                    }
                },
                {
                    "$sort": {"total_size_all_types": -1}
                }
            ]
            
            # Create the view
            mongo.db.create_collection("file_usage_summary", 
                                      viewOn="files", 
                                      pipeline=pipeline)
            
            print("File usage summary view created successfully")
            return True
            
        except Exception as e:
            print(f"Error creating file usage view: {e}")
            return False
    
    @staticmethod
    def create_all_views():
        """Create all database views"""
        print("Creating all database views...")
        
        results = {
            "conversation_summary": DatabaseViews.create_conversation_summary_view(),
            "user_activity": DatabaseViews.create_user_activity_view(),
            "group_analytics": DatabaseViews.create_group_analytics_view(),
            "file_usage": DatabaseViews.create_file_usage_view()
        }
        
        success_count = sum(results.values())
        total_count = len(results)
        
        print(f"Created {success_count}/{total_count} views successfully")
        
        if success_count < total_count:
            print("Failed views:", [name for name, success in results.items() if not success])
        
        return results
    
    @staticmethod
    def refresh_views():
        """Refresh all views by recreating them"""
        print("Refreshing all database views...")
        return DatabaseViews.create_all_views()
    
    @staticmethod
    def get_view_data(view_name, limit=None, skip=0):
        """Get data from a specific view with optional pagination"""
        try:
            collection = getattr(mongo.db, view_name)
            cursor = collection.find().skip(skip)
            
            if limit:
                cursor = cursor.limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            print(f"Error getting data from view {view_name}: {e}")
            return [] 