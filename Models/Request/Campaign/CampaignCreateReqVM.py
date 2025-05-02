from marshmallow import fields, Schema, validate

class CampaignCreateReqVM(Schema):
    campaignName = fields.Str(required=True)
    startDate = fields.Str(required=True)
    endDate = fields.Str(required=True)
    campaignFocus = fields.Str(required=True)
    location=fields.Str(required=True)
    budget=fields.Float(required=True)
    mediaPlan=fields.Str(required=True)
    