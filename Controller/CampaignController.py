from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from ..Models.Request.Campaign.CampaignCreateReqVM import CampaignCreateReqVM

class CampaignController:
    def __init__(self, campaignService):
        self.campaignBluePrint = Blueprint('campaign', __name__, url_prefix='/campaign')
        self.campaignService = campaignService
        self.setupRoute()
        
    def setupRoute(self):
        self.campaignBluePrint.route('', methods=['POST'])(self.create)
        
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