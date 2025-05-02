from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

class AgentController:
    def __init__(self, agentService):
        self.agentBluePrint = Blueprint('agent', __name__)
        self.agentService = agentService
        self.setup_routes()

    def setup_routes(self):
        self.agentBluePrint.route('/agent/<campaignId>', methods=['GET'])(self.getKeywords)
        self.agentBluePrint.route('/agent/ad-generator/<campaignId>', methods=['GET'])(self.getAd)

    def getKeywords(self, campaignId):
        try:
            print("Campaign ID:", campaignId)
            campaign = self.agentService.getCampaign(campaignId)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            business = self.agentService.getBusiness(campaignId)
            if not business:
                return jsonify({'error': 'Business not found'}), 404

            keywords, success = self.agentService.getKeywords(campaign, business)
            
            if success:
                return jsonify({'keywords': keywords}), 200
            return jsonify({'error': keywords}), 400
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    def getAd(self, campaignId):
        try:
            print("Campaign ID:", campaignId)
            campaign = self.agentService.getCampaign(campaignId)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404
            business = self.agentService.getBusiness(campaignId)
            if not business:
                return jsonify({'error': 'Business not found'}), 404
            # Get keywords
            keywords = self.agentService.getKeywordsFromDB(campaignId)
            if not keywords:
                return jsonify({'error': 'No keywords found for this campaign'}), 404
            # Generate ad using LLM
            ad_content, success = self.agentService.getAd(campaign, business, keywords)
            
            if success:
                return jsonify(ad_content), 200
            return jsonify({'error': ad_content}), 400

        except Exception as e:
            return jsonify({'error': str(e)}), 500