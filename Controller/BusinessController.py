from flask import Blueprint, request, jsonify
from ..Services.BusinessService import BusinessService
from marshmallow import ValidationError

from ..Models.Request.Business.BusinessCreateReqVM import BusinessCreateReqVM
class BusinessController:
    def __init__(self, business_service):
        self.businessBluePrint = Blueprint('business', __name__)
        self.businessService = business_service
        self.setup_routes()
        
    def setup_routes(self):
        self.businessBluePrint.route('/business', methods=['POST'])(self.create)
        
    def create(self):
        try:
            business_data = request.get_json()  
            businessCreateReqVM=BusinessCreateReqVM()
            businessCreateReqVM.load(business_data)
            result, success = self.businessService.create(business_data)
            
            if success:
                return jsonify(result), 200
            return jsonify({'error': result}), 400
            
        except ValidationError as e:
            # Handle marshmallow validation errors
            return jsonify({'error': 'Bad request'}), 400