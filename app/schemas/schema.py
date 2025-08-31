from marshmallow import Schema, fields, validate

class UserRegistrationSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=50))
    full_name = fields.Str(validate=validate.Length(max=100))
    
class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=50))

class UserProfileSchema(Schema):
    username = fields.Str(validate=validate.Length(min=3, max=50))
    email = fields.Email()
    full_name = fields.Str(validate=validate.Length(max=100))
    bio = fields.Str(validate=validate.Length(max=500))
    
class UserSettingsSchema(Schema):
    notifications_enabled = fields.Bool()
    read_receipts_enabled = fields.Bool()
    typing_indicators_enabled = fields.Bool()

class PasswordChangeSchema(Schema):
    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=6, max=50))

class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)

class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=6, max=50))

class ApiKeySchema(Schema):
    api_key = fields.Str(required=True, validate=validate.Length(min=1, max=500))