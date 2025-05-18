from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from ..Models.Request.Agents.AdGroupReqVM import AdGroupCreateReq
from ..SharedComponents.AuthToken import tokenRequired
class AgentController:
    def __init__(self, agentService):
        self.agentBluePrint = Blueprint('agent', __name__)
        self.agentService = agentService
        self.setup_routes()

    def setup_routes(self):
        self.agentBluePrint.route('/agent/<campaignId>', methods=['GET'])(self.getKeywords)
        self.agentBluePrint.route('/agent/ad-generator/<campaignId>', methods=['GET'])(self.getAd)
        self.agentBluePrint.route('/agent/launch-campaign/<user_id>', methods=['GET'])(self.launchCampaign)
        self.agentBluePrint.route('/agent/enable-campaign/<user_id>', methods=['GET'])(self.enable_campaign)
        self.agentBluePrint.route('/agent/create-ad-group', methods=['POST'])(self.create_ad_group)
        self.agentBluePrint.route('/agent/disable-campaign/<user_id>', methods=['GET'])(self.disable_campaign)

    @tokenRequired()
    def getKeywords(self, campaignId):
        try:
            print("Campaign ID:", campaignId)
            campaign = self.agentService.getCampaign(campaignId)
            print("Campaign:", campaign)
            adGroupId=self.agentService.getAdGroupIdByCampaignId(campaignId)
            print("Ad Group ID:", adGroupId)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            business = self.agentService.getBusiness(campaignId)
            if not business:
                return jsonify({'error': 'Business not found'}), 404

            keywords, success = self.agentService.getKeywords(campaign, business, adGroupId)
            
            if success:
                return jsonify({'keywords': keywords}), 200
            return jsonify({'error': keywords}), 400
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @tokenRequired()
    def getAd(self, campaignId):
        try:
            campaign = self.agentService.getCampaign(campaignId)
            adGroupId=self.agentService.getAdGroupIdByCampaignId(campaignId)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404
            business = self.agentService.getBusiness(campaignId)
            if not business:
                return jsonify({'error': 'Business not found'}), 404
            # Get keywords
            keywords = self.agentService.getKeywordsFromDB(adGroupId)
            print('keywords:', keywords)
            if not keywords:
                return jsonify({'error': 'No keywords found for this campaign'}), 404
            # Generate ad using LLM
            ad_content, success = self.agentService.getAd(campaign, business, keywords)
            
            if success:
                return jsonify(ad_content), 200
            return jsonify({'error': ad_content}), 400

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @tokenRequired()
    def launchCampaign(self,user_id):
        try:
            # Get userId from query parameters
            if not user_id:
                return jsonify({'error': 'userId is required'}), 400
            campaignId = request.args.get('campaignId')
            # 1. Get customer ID and create client
            customer_id = self.agentService.getCustomerId(user_id)
            if not customer_id:
                return jsonify({'error': 'Google Ads customer ID not found'}), 404

            # 2. Get campaign details
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            client=self.agentService.getClient(user_id)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            # 3. Create budget
            budget_resource = self.agentService.createBudget(client, user_id,campaignId)
            if not budget_resource:
                return jsonify({'error': 'Failed to create campaign budget'}), 400

            # 4. Create campaign
            campaign_resource = self.agentService.createCampaign(client, user_id,campaignId)
            if not campaign_resource:
                return jsonify({'error': 'Failed to create campaign'}), 400
            print("Campaign resource:", campaign_resource)
            ad_group_resource = self.agentService.createAdGroup(
                client,
                customer_id,
                campaign_resource,
                campaignId
            )
            if not ad_group_resource:
                return jsonify({'error': 'Failed to create ad group'}), 400

            # 6. Create responsive search ads
            ad_resources = self.agentService.createResponsiveSearchAds(
                client,
                customer_id,
                ad_group_resource,
                campaign['_id']
            )
            
            # 7. Return success response with created resources
            return jsonify({
                'message': 'Campaign launched successfully',
                'resources': {
                    'budget': budget_resource,
                    'campaign': campaign_resource,
                    'adGroup': ad_group_resource,
                    'ads': ad_resources
                }
            }), 200

        except Exception as e:
            print(f"Error launching campaign: {str(e)}")
            return jsonify({'error': str(e)}), 500    
    @tokenRequired()
    def enable_campaign(self,user_id):
        try:
            campaignId = request.args.get('campaignId')
            client = self.agentService.getClient(user_id)
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            
            if not campaign.get('resourceName'):
                raise Exception("Campaign resource name not found")
                
            response = self.agentService.enable_campaign(
                client, 
                user_id, 
                campaignId
            )
            
            
            return {"message": "Campaign enabled successfully"},200
            
        except Exception as e:
            return {"error": str(e)}, 400
    @tokenRequired()
    def create_ad_group(self):
        try:
            data = request.get_json()
            try:
                adGroupCreateReq=AdGroupCreateReq
                # Validate the request data
                adGroupCreateReq().load(data)
            except ValidationError as err:  
                return jsonify({'error': 'bad request'}), 400
                  
            self.agentService.storeAdGroup(data)
            return jsonify({
                'status': 'success',
            }), 201
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @tokenRequired()
    def disable_campaign(self, user_id):
        try:
            campaignId = request.args.get('campaignId')
            client = self.agentService.getClient(user_id)
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            
            if not campaign.get('resourceName'):
                raise Exception("Campaign resource name not found")
                
            response = self.agentService.disable_campaign(
                client, 
                user_id, 
                campaignId
            )
            
            return {"message": "Campaign disabled successfully"}, 200
            
        except Exception as e:
            return {"error": str(e)}, 400