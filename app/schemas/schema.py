from marshamallow import Schema, fields , validate

class UserRegistrationSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=50))
    full_name = fields.Str(validate=validate.Length(max=100))
    
class UserLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=6, max=50))