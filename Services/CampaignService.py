from bson import ObjectId
from datetime import datetime
from ..database import mongo
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.chains import LLMChain
from bson import ObjectId
from ..config import AzureDeploymentName, AzureOpenAiVersion, AzureOpenAiKey, AzureOpenAiEndpoint
from  langchain_openai import AzureChatOpenAI
import json
from google.ads.googleads.client import GoogleAdsClient
from ..config import GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from google.protobuf import field_mask_pb2
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate
)
from .client import RestClient
import time


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
            campaign_data['budget'] =campaign_data['budget']*1000000 # Ensure budget is a float
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
            adGroups=self.createAdGroup(campaign_data)


            return {
                'message': 'Campaign created successfully',
                'campaignId': str(result.inserted_id),
                'adGroups': adGroups['adGroups'] if 'adGroups' in adGroups else []
            }, 201

        except Exception as e:
            print(f"Error creating campaign: {str(e)}")
            return {'error': str(e)}, 500
        
    def createAdGroup(self, campaignData):
        try:
            # Initialize LLM
            chat_llm = AzureChatOpenAI(
                deployment_name=AzureDeploymentName,
                openai_api_version=AzureOpenAiVersion,
                openai_api_key=AzureOpenAiKey,
                azure_endpoint=AzureOpenAiEndpoint,
                temperature=0.0,
            )

            # Create prompt template
            prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""
You are a Google Ads expert. Based on the campaign data, create ad groups in this exact JSON format:
{{
    "adGroups": [
        {{
            "name": "Example Ad Group",
            "type": "SEARCH_STANDARD",
            "cpcBidMicros": 2000000
        }}
    ]
}}

Rules:
1. Return ONLY the JSON object—no additional text or formatting.
2. Each ad group must have exactly these fields: name, type, cpcBidMicros.
3. type must be "SEARCH_STANDARD".
4. cpcBidMicros must be a multiple of 1,000,000 (i.e., whole-dollar bids) and between 1,000,000 (USD 1) and 10,000,000 (USD 10).
5. Create 2–5 ad groups based on campaign scope.
"""),
    HumanMessagePromptTemplate.from_template("""
Campaign Details:
Name: {campaignName}
Focus: {conversionFocus}
Budget: ${budget}
Location: {location}
Objectives: {objectives}
""")
])
            # Invoke LLM
            ad_group_chain = LLMChain(llm=chat_llm, prompt=prompt)
            result = ad_group_chain.invoke({
                'campaignName': campaignData['campaignName'],
                'conversionFocus': campaignData.get('conversionFocus', ''),
                'budget': campaignData.get('budget', 0),
                'location': campaignData.get('location', ''),
                'objectives': campaignData.get('objectives', '')
            })

            # Parse LLM response
            try:
                if isinstance(result, dict) and 'text' in result:
                    # Clean up the response text
                    json_str = result['text'].strip()
                    if json_str.startswith('```json'):
                        json_str = json_str[7:-3]  # Remove ```json and ``` markers
                    ad_groups_data = json.loads(json_str)
                else:
                    ad_groups_data = json.loads(result.content)

                if 'adGroups' not in ad_groups_data:
                    raise ValueError("LLM response missing 'adGroups' key")

                # Store ad groups in MongoDB
                stored_ad_groups = []
                for ad_group in ad_groups_data['adGroups']:
                    ad_group_document = {
                        'name': ad_group['name'],
                        'type': ad_group['type'],
                        'cpcBidMicros': ad_group['cpcBidMicros'],
                        'cpcBidMicros': ad_group['cpcBidMicros'],
                        'campaignId': campaignData['_id'],  # Already an ObjectId from create()
                        'status': 'PENDING',
                        'createdAt': datetime.utcnow(),
                        'updatedAt': datetime.utcnow()
                    }
                    
                    result = mongo.db.AdGroup.insert_one(ad_group_document)
                    stored_ad_groups.append({
                        "id":str(result.inserted_id),
                        "name": ad_group['name'],

                    }
                    )

                return {
                    'adGroups': stored_ad_groups
                }

            except json.JSONDecodeError as e:
                print(f"Error parsing LLM response: {str(e)}")
                print(f"Raw response: {result}")
                raise ValueError("Invalid JSON response from LLM")
            except KeyError as e:
                print(f"Missing required field in response: {str(e)}")
                raise ValueError(f"Missing required field in LLM response: {str(e)}")

        except Exception as e:
            print(f"Error creating ad groups: {str(e)}")
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

    def reviewCampaign(self, campaign_id: str, ad_group_ids: list) -> dict:
        try:
            # Get campaign details
            campaign = mongo.db.Campaigns.find_one(
                {'_id': ObjectId(campaign_id)},
                {'campaignName': 1}
            )
            
            if not campaign:
                return None

            # Get ad groups with their keywords
            ad_groups = []
            for ad_group_id in ad_group_ids:
                # Get ad group details
                ad_group = mongo.db.AdGroup.find_one(
                    {'_id': ObjectId(ad_group_id)},
                    {'name': 1, 'keywords': 1}
                )
                
                if ad_group:
                    # Get ads for this ad group
                    ads = list(mongo.db.Ads.find(
                        {'adGroupId': ObjectId(ad_group_id)},
                        {
                            'headlines': 1,
                            'descriptions': 1
                        }
                    ))
                    
                    ad_groups.append({
                        'adGroupId': str(ad_group['_id']),
                        'name': ad_group['name'],
                        'ads': [{
                            'headlines': ad['headlines'],
                            'descriptions': ad['descriptions'],
                            'keywords': ad_group.get('keywords'),

                        } for ad in ads]
                    })

            # Construct response
            return {
                'campaignId': str(campaign['_id']),
                'campaignName': campaign['campaignName'],
                'adGroups': ad_groups
            }

        except Exception as e:
            print(f"Error in reviewCampaign service: {str(e)}")
            raise