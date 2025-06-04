from flask import Blueprint, jsonify, request
from ..Services.DashboardService import DashboardService
from ..SharedComponents.AuthToken import tokenRequired
from datetime import datetime, timedelta

class DashboardController:
    def __init__(self, dashboardService: DashboardService):
        self.dashboardBluePrint = Blueprint('dashboard', __name__, url_prefix='/dashboard')
        self.dashboardService = dashboardService
        self.setupRoutes()
        
    def setupRoutes(self):
        self.dashboardBluePrint.route('/campaigns', methods=['POST'])(self.getCampaignMetrics)
        self.dashboardBluePrint.route('/summary', methods=['POST'])(self.getSummaryMetrics)

    @tokenRequired()
    def getCampaignMetrics(self):
        try:
            # Get userId from token (set by tokenRequired decorator)
            data=request.get_json()
            user_id=data['userId']
            customer_id=data['customerId']            
            
            # Get campaign metrics from service
            metrics = self.dashboardService.getCampaignMetrics(user_id,customer_id)
            
            return jsonify(metrics), 200
            
        except Exception as e:
            print(f"Error fetching campaign metrics: {str(e)}")
            return jsonify({'error': str(e)}), 500
    @tokenRequired()
    @tokenRequired()
    def getSummaryMetrics(self):
        try:
            data = request.get_json()
            user_id = data['userId']
            customer_id = data['customerId']
            
            # Get metrics from service
            summary_metrics = self.dashboardService.getSummaryMetrics(user_id, customer_id)
            
            return jsonify(summary_metrics), 200
            
        except Exception as e:
            print(f"Error fetching summary metrics: {str(e)}")
            return jsonify({'error': str(e)}), 500