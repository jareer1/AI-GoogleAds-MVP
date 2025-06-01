from marshmallow import fields, Schema, validate

class AdScheduleSchema(Schema):
    dayOfWeek = fields.Int(required=True)
    startHour = fields.Int(required=True)
    endHour = fields.Int(required=True)

class CampaignCreateReqVM(Schema):
    campaignName = fields.Str(required=True)
    startDate = fields.Str(required=True)
    endDate = fields.Str(required=True)
    conversionFocus = fields.Str(required=True)
    location=fields.Str(required=True)
    objectives=fields.Str(required=True)
    biddingStrategy=fields.Str(required=True)
    budget=fields.Float(required=False)
    userId=fields.Str(required=True)
    adScheduling = fields.List(fields.Nested(AdScheduleSchema), required=False)    
    networks=fields.List(fields.Str(), required=True)
    language=fields.Str(required=True)
    customerId=fields.Str(required=True)