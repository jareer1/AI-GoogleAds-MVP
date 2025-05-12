from marshmallow import Schema, fields, validate

class UserSignupReqVM(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)