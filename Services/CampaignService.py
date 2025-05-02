from ..database import mongo
from flask import request, jsonify
from datetime import datetime

class CampaignService:
    @staticmethod
    def create(campaign_data):
        try:

            campaign_data['startDate'] = datetime.strptime(campaign_data['startDate'], '%Y-%m-%d')
            campaign_data['endDate'] = datetime.strptime(campaign_data['endDate'], '%Y-%m-%d')

            # Add creation timestamp
            campaign_data['createdAt'] = datetime.utcnow()

            # Insert into MongoDB
            result = mongo.db.Campaigns.insert_one(campaign_data)

            return {
                'message': 'Campaign created successfully',
                'campaignId': str(result.inserted_id)
            }, 201

        except Exception as e:
            return {'error': str(e)}, 500
