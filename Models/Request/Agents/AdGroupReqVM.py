from marshmallow import fields, Schema, validate

class AdGroupCreateReq(Schema):
    name = fields.Str(required=True)
    type = fields.Str(required=True)
    cpcBidMicros = fields.Int(required=True)
    campaignId= fields.Str(required=True)