# models.py
from flask_login import UserMixin
from bson.objectid import ObjectId
from database import users_collection

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.hashed_password = user_data['hashed_password']
        self.group = user_data['group']
        # Load custom permissions list (defaults to empty if not found)
        self.permissions = user_data.get('permissions', [])

    def has_permission(self, perm_name):
        """
        Checks if the user has a specific permission.
        Owners ALWAYS return True (God Mode).
        """
        if self.group == 'Owner':
            return True
        return perm_name in self.permissions

    @staticmethod
    def find_by_username(username):
        user_data = users_collection.find_one({'username': username})
        if user_data:
            return User(user_data)
        return None

    @staticmethod
    def find_by_id(user_id):
        user_data = users_collection.find_one({'_id': ObjectId(user_id)})
        if user_data:
            return User(user_data)
        return None