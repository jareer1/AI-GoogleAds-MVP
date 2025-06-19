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
        self.agentBluePrint.route('/agent/ad-generator/<user_id>', methods=['POST'])(self.getAd)
        self.agentBluePrint.route('/agent/launch-campaign/<user_id>', methods=['GET'])(self.launchCampaign)
        self.agentBluePrint.route('/agent/enable-campaign/<user_id>', methods=['GET'])(self.enable_campaign)
        self.agentBluePrint.route('/agent/create-ad-group', methods=['POST'])(self.create_ad_group)
        self.agentBluePrint.route('/agent/disable-campaign/<user_id>', methods=['GET'])(self.disable_campaign)
        self.agentBluePrint.route('/agent/save-ad', methods=['POST'])(self.saveAd)


    @tokenRequired()
    def saveKeywords(self):
        try:
            data = request.get_json()['keywordGroups']
            
            # Save each group of keywords
            results = []
            for group in data:
                success = self.agentService.saveKeywords(
                    group['keywords'],
                    adGroupId=group['adGroupId']
                )
                results.append({
                    'adGroupId': group['adGroupId'],
                    'success': success
                })
            
            # Check if all saves were successful
            if all(r['success'] for r in results):
                return jsonify({
                    'message': 'All keywords saved successfully',
                    'results': results
                }), 201
            
            return jsonify({
                'error': 'Some keywords failed to save',
                'results': results
            }), 400
                
        except Exception as e:
            print(f"Error saving keywords: {str(e)}")
            return jsonify({'error': str(e)}), 500
    @tokenRequired()
    def getKeywords(self, campaignId):
        try:
            data = request.get_json()
            campaign = self.agentService.getCampaign(campaignId)

            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404


            business = self.agentService.getBusiness(data['userId'])
            if not business:
                return jsonify({'error': 'Business not found'}), 404

            # Process each ad group and collect keywords
            keywords_by_group = []
            website = data.get('website', None)
            for adGroupId in data['adGroupIds']:
                keywords, success = self.agentService.getKeywords(
                    campaign=campaign,
                    business=business,
                    adGroupId=adGroupId,
                    checkWebsite=data['checkWebsite'],
                    keywords=data['keywords'],
                    website=website,
                )
                
                if success:
                    keywords_by_group.append({
                        'adGroupId': adGroupId,
                        'keywords': keywords
                    })
                else:
                    return jsonify({'error': f'Failed to get keywords for ad group: {adGroupId}'}), 400

            return jsonify({
                'keywordGroups': keywords_by_group
            }), 200

        except Exception as e:
            print(f"Error getting keywords: {str(e)}")
            return jsonify({'error': str(e)}), 500    
    @tokenRequired()
    def getAd(self, user_id):
        try:
            campaignId = request.args.get('campaignId')
            campaign = self.agentService.getCampaign(campaignId)
            adGroupIds = request.get_json()['adGroupIds']

            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            business = self.agentService.getBusiness(user_id)
            if not business:
                return jsonify({'error': 'Business not found'}), 404

            # Process each ad group and collect ads
            ad_contents = []
            for adGroupId in adGroupIds:
                keywords = self.agentService.getKeywordsFromDB(adGroupId)
                
                if not keywords:
                    return jsonify({'error': f'No keywords found for ad group: {adGroupId}'}), 404
                
                # Generate ad using LLM
                ad_content, success = self.agentService.getAd(campaign, business, keywords, adGroupId)
                
                if success:
                    ad_contents.append({
                        'adGroupId': adGroupId,
                        'adContent': ad_content
                    })
                else:
                    return jsonify({'error': f'Failed to generate ad for ad group: {adGroupId}'}), 400

            return jsonify({
                'ads': ad_contents
            }), 200

        except Exception as e:
            print(f"Error generating ads: {str(e)}")
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
            adGroupIds=self.agentService.getAdGroupIdByCampaignId(campaignId)
            for adGroupId in adGroupIds:
                ad_group_resource = self.agentService.createAdGroup(
                    client,
                    customer_id,
                    campaign_resource,
                    campaignId,
                    adGroupId
                )
                if not ad_group_resource:
                    return jsonify({'error': 'Failed to create ad group'}), 400
                
            # 6. Create responsive search ads
                ad_resources = self.agentService.createResponsiveSearchAds(
                    client,
                    customer_id,
                    ad_group_resource,
                    user_id,
                    adGroupId
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
            data=request.get_json()
            ads_data = data['ads']
            campaignId = data.get('campaignId')
            for ad_data in ads_data:
                  
                success = self.agentService.saveAd(ad_data,campaignId)
            
                
                if not success:
                    return jsonify({
                        'error': 'Failed to save ad'
                    }), 400
            return jsonify({
                        'message': 'Ad saved successfully'}), 201
        except Exception as e:
            print(f"Error saving ad: {str(e)}")
            return jsonify({'error': str(e)}), 500