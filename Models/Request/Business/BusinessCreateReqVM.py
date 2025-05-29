from marshmallow import fields, Schema, validate


class BusinessCreateReqVM(Schema):
    businessName = fields.Str(required=True,)
    role = fields.Str(required=True)
    # phoneNumber = fields.Str(required=True)
    websiteUrl = fields.Str(required=True)
    # operatingHours = fields.Dict(required=True)
    mainCategory = fields.Str(required=True)
    sizeofCompany = fields.Str(required=True)
    # serviceAreas = fields.List(fields.Str(),required=False)
    # campaignId = fields.Str(required=True)
