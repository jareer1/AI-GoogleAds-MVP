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
        self.dashboardBluePrint.route('/campaigns', methods=['GET'])(self.getCampaignMetrics)
        self.dashboardBluePrint.route('/summary', methods=['GET'])(self.getSummaryMetrics)

    @tokenRequired()
    def getCampaignMetrics(self):
        try:
            # Get userId from token (set by tokenRequired decorator)
            user_id = request.userId
            
            # Get campaign metrics from service
            metrics = self.dashboardService.getCampaignMetrics(user_id)
            
            return jsonify(metrics), 200
            
        except Exception as e:
            print(f"Error fetching campaign metrics: {str(e)}")
            return jsonify({'error': str(e)}), 500
    @tokenRequired()
    def getSummaryMetrics(self):
        try:
            # Get userId from token
            user_id = request.userId
            
            # Parse query parameters with defaults
            try:
                start_date = datetime.strptime(
                    request.args.get('startDate', (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')),
                    '%Y-%m-%d'
                )
                end_date = datetime.strptime(
                    request.args.get('endDate', datetime.utcnow().strftime('%Y-%m-%d')),
                    '%Y-%m-%d'
                )
                compare = request.args.get('compare', 'true').lower() == 'true'
            except ValueError as e:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
            metrics = self.dashboardService.getSummaryMetrics(
                user_id,
                start_date,
                end_date,
                compare
            )
            
            return jsonify(metrics), 200
            
        except Exception as e:
            print(f"Error fetching summary metrics: {str(e)}")
            return jsonify({'error': str(e)}), 500