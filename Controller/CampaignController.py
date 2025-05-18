from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from ..Models.Request.Campaign.CampaignCreateReqVM import CampaignCreateReqVM
from ..SharedComponents.AuthToken import tokenRequired
class CampaignController:
    def __init__(self, campaignService):
        self.campaignBluePrint = Blueprint('campaign', __name__, url_prefix='/campaign')
        self.campaignService = campaignService
        self.setupRoute()
        
    def setupRoute(self):
        self.campaignBluePrint.route('', methods=['POST'])(self.create)
        self.campaignBluePrint.route('/<campaign_id>', methods=['PUT'])(self.update)
        self.campaignBluePrint.route('/<campaign_id>', methods=['GET'])(self.getCampaign)
        self.campaignBluePrint.route('/<campaign_id>', methods=['DELETE'])(self.deleteCampaign)
        self.campaignBluePrint.route('/all/<user_id>', methods=['GET'])(self.getAllCampaigns)
    
    @tokenRequired()
    def create(self):
        try:
            campaignData = request.get_json()
            if not campaignData:
                return jsonify({'error': 'No data provided'}), 400

            campaignCreateReqVM = CampaignCreateReqVM()
            # Validate data against schema
            validated_data = campaignCreateReqVM.load(campaignData)
            
            # Pass validated data to service
            msg, isSuccessful = self.campaignService.create(validated_data)
            
            if isSuccessful:
                return jsonify({'message': msg}), 201  # Changed to 201 for resource creation
            return jsonify({'error': msg}), 400
            
        except ValidationError as e:
            # Handle marshmallow validation errors
            return jsonify({'error': 'Bad request'}), 400
    
    @tokenRequired()
    def update(self, campaign_id):
        try:
            # Get and validate request data
            campaign_data = request.get_json()
            if not campaign_data:
                return jsonify({'error': 'No data provided'}), 400

            # Validate schema
            campaign_update_vm = CampaignCreateReqVM()  # Reusing create schema
            validated_data = campaign_update_vm.load(campaign_data)
            
            # Check if campaign exists
            exists = self.campaignService.checkCampaign(campaign_id)
            if not exists:
                return jsonify({'error': 'Campaign not found'}), 404

            # Update campaign
            msg, isSuccessful = self.campaignService.update(campaign_id, validated_data)
            
            if isSuccessful:
                return jsonify({'message': msg}), 200
            return jsonify({'error': msg}), 400

        except ValidationError as e:
            return jsonify({'error': 'Bad request'}), 400
        except Exception as e:
            print(f"Error updating campaign: {str(e)}")
            return jsonify({'error': str(e)}), 500

    @tokenRequired()    
    def getCampaign(self,campaign_id):
        try:
            # Get campaign by ID
            campaign = self.campaignService.getCampaign(campaign_id)
            if not campaign:
                return jsonify({'error': 'Campaign not found'}), 404

            return jsonify(campaign), 200

        except Exception as e:
            print(f"Error retrieving campaign: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    
    @tokenRequired()
    def getAllCampaigns(self,user_id):
        try:
            campaigns = self.campaignService.getAllCampaigns(user_id)
            return jsonify(campaigns), 200

        except Exception as e:
            print(f"Error retrieving campaigns: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @tokenRequired()
    def deleteCampaign(self,campaign_id):
        try:
            # Check if campaign exists
            exists = self.campaignService.checkCampaign(campaign_id)
            if not exists:
                return jsonify({'error': 'Campaign not found'}), 404

            # Delete campaign
            msg, isSuccessful = self.campaignService.delete(campaign_id)
            
            if isSuccessful:
                return jsonify({'message': msg}), 200
            return jsonify({'error': msg}), 400

        except Exception as e:
            print(f"Error deleting campaign: {str(e)}")
            return jsonify({'error': str(e)}), 500