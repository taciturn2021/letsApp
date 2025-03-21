# Models package initialization
from app.models.user import User
from app.models.message import Message
from app.models.group import Group
from app.models.group_message import GroupMessage
from app.models.contact import Contact
from app.models.file import File
from app.models.presence import Presence

# Export all models
__all__ = ['User', 'Message', 'Group', 'GroupMessage', 'Contact', 'File', 'Presence']
