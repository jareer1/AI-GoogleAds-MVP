from marshmallow import fields, Schema, validate

class ScheduleSchema(Schema):
    day_of_week = fields.Str(required=True)
    start_hour = fields.Int(required=True)
    end_hour = fields.Int(required=True)

class CalloutSchema(Schema):
    text = fields.Str(required=False)
    schedule = fields.Nested(ScheduleSchema, required=False)

class SitelinkSchema(Schema):
    text = fields.Str(required=False)
    final_url = fields.Str(required=False)
    description_1 = fields.Str(required=False)
    description_2 = fields.Str(required=False)
    schedule = fields.Nested(ScheduleSchema, required=False)


class AdReqVM(Schema):
    headlines = fields.List(fields.Str(), required=True)
    descriptions = fields.List(fields.Str(), required=True)
    campaignId = fields.Str(required=True)
    callouts = fields.List(fields.Nested(CalloutSchema), required=False)
    sitelinks = fields.List(fields.Nested(SitelinkSchema), required=False)
