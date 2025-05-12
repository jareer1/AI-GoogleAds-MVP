from bson import ObjectId
from ..database import mongo
from flask import request, jsonify
from datetime import datetime

class CampaignService:
    def check_duplicate_campaign_name(self, user_id: str, campaign_name: str, exclude_campaign_id: str = None) -> bool:
        """Check if campaign name already exists for user"""
        try:
            query = {
                'userId': ObjectId(user_id),
                'campaignName': campaign_name
            }
            
            # If updating, exclude current campaign
            if exclude_campaign_id:
                query['_id'] = {'$ne': ObjectId(exclude_campaign_id)}
                
            existing_campaign = mongo.db.Campaigns.find_one(query)
            return existing_campaign is not None
            
        except Exception as e:
            print(f"Error checking duplicate campaign name: {str(e)}")
            raise
    def create(self,campaign_data):
        try:
            if self.check_duplicate_campaign_name(
                campaign_data['userId'], 
                campaign_data['campaignName']
            ):
                return {
                    'error': 'Campaign name already exists for this user'
                }, 400

            # Convert string dates to datetime objects
            campaign_data['startDate'] = datetime.strptime(campaign_data['startDate'], '%Y-%m-%d')
            campaign_data['endDate'] = datetime.strptime(campaign_data['endDate'], '%Y-%m-%d')

            # Convert userId string to ObjectId
            campaign_data['userId'] = ObjectId(campaign_data['userId'])

            # Add metadata
            campaign_data.update({
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow(),
                'status': 'DRAFT'
            })

            # Insert into MongoDB
            result = mongo.db.Campaigns.insert_one(campaign_data)

            return {
                'message': 'Campaign created successfully',
                'campaignId': str(result.inserted_id)
            }, 201

        except Exception as e:
            print(f"Error creating campaign: {str(e)}")
            return {'error': str(e)}, 500

    def update(self, campaign_id: str, campaign_data: dict) -> tuple[str, bool]:
        """Update an existing campaign"""
        try:
            # Check for duplicate campaign name if name is being updated
            if 'campaignName' in campaign_data:
                campaign = self.getCampaign(campaign_id)
                if self.check_duplicate_campaign_name(
                    str(campaign['userId']), 
                    campaign_data['campaignName'],
                    campaign_id
                ):
                    return 'Campaign name already exists', False

            # Add metadata
            campaign_data.update({
                'updatedAt': datetime.utcnow()
            })

            # Update in MongoDB
            result = mongo.db.Campaigns.update_one(
                {'_id': ObjectId(campaign_id)},
                {'$set': campaign_data}
            )

            if result.modified_count > 0:
                return 'Campaign updated successfully', True
            return 'No changes made to campaign', False

        except Exception as e:
            print(f"Error updating campaign: {str(e)}")
            raise
    def checkCampaign(self, campaign_id: str) -> bool:
        try:
            campaign = mongo.db.Campaigns.find_one({'_id': ObjectId(campaign_id)})
            if campaign:
                return True
            return False
        except Exception as e:
            print(f"Error checking campaign: {str(e)}")
            raise

    def getCampaign(self, campaign_id: str) -> dict:
        try:
            campaign = mongo.db.Campaigns.find_one({'_id': ObjectId(campaign_id)})
            if campaign:
                campaign['_id'] = str(campaign['_id'])
                campaign['userId'] = str(campaign['userId'])  # Convert ObjectId to string
                return campaign
            return None

        except Exception as e:
            print(f"Error fetching campaign: {str(e)}")
            raise
    def getAllCampaigns(self, user_id: str) -> list:
        try:
            campaigns = mongo.db.Campaigns.find({'userId': ObjectId(user_id)})
            return [dict(campaign, _id=str(campaign['_id']), userId=str(campaign['userId'])) for campaign in campaigns]

        except Exception as e:
            print(f"Error fetching all campaigns: {str(e)}")
            raise
    def delete(self, campaign_id: str) -> tuple[str, bool]:
        try:
            result = mongo.db.Campaigns.delete_one({'_id': ObjectId(campaign_id)})

            if result.deleted_count > 0:
                return 'Campaign deleted successfully', True
            return 'Campaign not found', False

        except Exception as e:
            print(f"Error deleting campaign: {str(e)}")
            raise