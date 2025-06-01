from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from ..Models.Request.Agents.AdGroupReqVM import AdGroupCreateReq
from ..SharedComponents.AuthToken import tokenRequired
from ..Models.Request.Agents.AdReqVM import AdReqVM
class AgentController:
    def __init__(self, agentService):
        self.agentBluePrint = Blueprint('agent', __name__)
        self.agentService = agentService
        self.setup_routes()

    def setup_routes(self):
        self.agentBluePrint.route('/agent/keywords', methods=['POST'])(self.saveKeywords)
        self.agentBluePrint.route('/agent/<campaignId>', methods=['POST'])(self.getKeywords)
        self.agentBluePrint.route('/agent/ad-generator/<user_id>', methods=['GET'])(self.getAd)
        self.agentBluePrint.route('/agent/launch-campaign/<user_id>', methods=['GET'])(self.launchCampaign)
        self.agentBluePrint.route('/agent/enable-campaign/<user_id>', methods=['GET'])(self.enable_campaign)
        self.agentBluePrint.route('/agent/create-ad-group', methods=['POST'])(self.create_ad_group)
        self.agentBluePrint.route('/agent/disable-campaign/<user_id>', methods=['GET'])(self.disable_campaign)
        self.agentBluePrint.route('/agent/save-ad', methods=['POST'])(self.saveAd)


    @tokenRequired()
    def saveKeywords(self):
        data=request.get_json()
        success = self.agentService.saveKeywords(data['keywords'], data['adGroupId'])
        if success:
            return jsonify({'message': 'Keywords saved successfully'}), 201
        else:
            return jsonify({'error': 'Failed to save keywords'}), 400

    @tokenRequired()
    def getKeywords(self, campaignId):
        try:
            data=request.get_json()
            campaign = self.agentService.getCampaign(campaignId)
            adGroupId=data['adGroupId']
            checkWebsite=data['checkWebsite']
            keywords=data['keywords']
            userId=data['userId']
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            business = self.agentService.getBusiness(userId)
            if not business:
                return jsonify({'error': 'Business not found'}), 404

            keywords, success = self.agentService.getKeywords(campaign, business, adGroupId,checkWebsite,keywords)
            
            if success:
                return jsonify({'keywords': keywords}), 200
            return jsonify({'error': keywords}), 400
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @tokenRequired()
    def getAd(self, user_id):
        try:
            campaignId = request.args.get('campaignId')
            campaign = self.agentService.getCampaign(campaignId)
            adGroupId=self.agentService.getAdGroupIdByCampaignId(campaignId)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404
            business = self.agentService.getBusiness(user_id)
            if not business:
                return jsonify({'error': 'Business not found'}), 404
            # Get keywords
            keywords = self.agentService.getKeywordsFromDB(adGroupId)
            print(f"Keywords for ad generation: {keywords}")
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
            customer_id = self.agentService.getCustomerId(campaignId)
            if not customer_id:
                return jsonify({'error': 'Google Ads customer ID not found'}), 404

            # 2. Get campaign details
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            client=self.agentService.getClient(user_id,customer_id)
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
                campaign['_id'],
                user_id
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
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            customerId=campaign['customerId']
            client = self.agentService.getClient(user_id, customerId)
            
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
                return jsonify({'error': 'Bad Request'}), 400
                  
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
            campaign = self.agentService.getCampaignByCampaignId(campaignId)
            customerId = campaign.get('customerId', None)
            client = self.agentService.getClient(user_id,customerId)
            
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
    @tokenRequired()
    def saveAd(self):
        try:
            # Get request data
            ad_data = request.get_json()
            
            if not ad_data:
                return jsonify({'error': 'No ad data provided'}), 400
                
            try:
                adReqVM=AdReqVM()
                ad_data = adReqVM.load(ad_data)
            except ValidationError as err:
                return jsonify({'error': 'Bad Request', 'details': err.messages}), 400
                
            # Call service method to save ad
            success = self.agentService.saveAd(ad_data)
            
            if success:
                return jsonify({
                    'message': 'Ad saved successfully'}), 201
            else:
                return jsonify({
                    'error': 'Failed to save ad'
                }), 400
                
        except Exception as e:
            print(f"Error saving ad: {str(e)}")
            return jsonify({'error': str(e)}), 500