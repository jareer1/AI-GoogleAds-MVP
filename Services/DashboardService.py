from datetime import datetime, timedelta
from typing import List, Dict
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from bson import ObjectId
from ..database import mongo
import time

class DashboardService:
    def __init__(self, agentService):
        self.agentService = agentService  # For getting Google Ads client
        
    def getCampaignMetrics(self, user_id,customer_id):
        try:
            # Get all campaigns for user
            campaigns = self.getUserCampaigns(user_id,customer_id)
            if not campaigns:
                return []
            metrics = []
            yesterday = datetime.utcnow() - timedelta(days=1)

            for campaign in campaigns:
                # Always include status in the response
                base_response = {
                    'campaignId': str(campaign['_id']),
                    'campaignName': campaign['campaignName'],
                    'status': campaign.get('status', 'UNKNOWN')
                }

                # If resourceName does not exist, return zeroed metrics
                if 'resourceName' not in campaign or not campaign['resourceName']:
                    zero_metrics = {
                        'cost': 0.0,
                        'conversions': 0,
                        'impressions': 0,
                        'clicks': 0,
                        'avgCpc': 0.0,
                        'cpa': 0.0,
                        'interactionRate': 0.0,
                        'interactions': 0
                    }
                    metrics.append({**base_response, **zero_metrics})
                    continue

                # Check for existing metrics
                stored_metrics = self.getStoredMetrics(campaign['_id'], yesterday)

                if stored_metrics:
                    metrics.append({**base_response, **stored_metrics})
                else:
                    # Fetch fresh metrics from Google Ads
                    fresh_metrics = self.fetchGoogleAdsMetrics(
                        user_id,
                        campaign['resourceName'],
                        customer_id
                    )

                    # Store new metrics
                    self.storeMetrics(campaign['_id'], fresh_metrics)

                    metrics.append({**base_response, **fresh_metrics})

            return metrics

        except Exception as e:
            print(f"Error processing campaign: {str(e)}")
            raise Exception(f"Error processing campaign: {str(e)}")                    
            
    def getUserCampaigns(self, user_id,customer_id):
        return list(mongo.db.Campaigns.find({'userId': ObjectId(user_id),'customerId': customer_id}))
        
    def getStoredMetrics(self, campaign_id: ObjectId, since_date: datetime):
        # Ensure since_date is at midnight for proper comparison
        since_date = since_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        metrics = mongo.db.PerformanceMetrics.find_one({
            'campaignId': campaign_id,
            'date': {'$gte': since_date}
        })
        
        if metrics:
            return {
                'cost': metrics['cost'],
                'conversions': metrics['conversions'],
                'impressions': metrics['impressions'],
                'clicks': metrics['clicks'],
                'avgCpc': metrics['avgCpc'],
                'cpa': metrics['cpa'],
                'interactionRate': metrics['interactionRate'],
                'interactions': metrics['interactions']
            }
        return None
        
    def storeMetrics(self, campaign_id: ObjectId, metrics: Dict):
        current_date = datetime.utcnow()
        current_date = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        mongo.db.PerformanceMetrics.update_one(
            {
                'campaignId': campaign_id,
                'date': current_date  # Using datetime instead of date
            },
            {
                '$set': {
                    **metrics,
                    'updatedAt': datetime.utcnow()
                }
            },
            upsert=True
        )
            
    def fetchGoogleAdsMetrics(self, user_id, campaign_resource_name, customerId):
        max_retries = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                client = self.agentService.getClient(user_id, customerId)
                
                ga_service = client.get_service("GoogleAdsService")
                
                query = """
                    SELECT 
                        campaign.id,
                        metrics.cost_micros,
                        metrics.conversions,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.average_cpc,
                        metrics.cost_per_conversion,
                        metrics.interaction_rate,
                        metrics.interactions
                    FROM campaign
                    WHERE campaign.resource_name = '%s'
                    AND segments.date DURING LAST_7_DAYS
                """ % campaign_resource_name
                
                response = ga_service.search(
                    customer_id=customerId,
                    query=query
                )
                
                # Process the first row (should only be one)
                for row in response:
                    return {
                        'cost': row.metrics.cost_micros / 1_000_000,  # Convert micros to actual currency
                        'conversions': row.metrics.conversions,
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'avgCpc': row.metrics.average_cpc / 1_000_000,  # Convert micros to actual currency
                        'cpa': row.metrics.cost_per_conversion / 1_000_000 if row.metrics.conversions > 0 else 0,
                        'interactionRate': float(row.metrics.interaction_rate),
                        'interactions': row.metrics.interactions
                    }
                    
                # return {
                #     'cost': 0.0,
                #     'conversions': 0,
                #     'impressions': 0,
                #     'clicks': 0,
                #     'avgCpc': 0.0,
                #     'cpa': 0.0,
                #     'interactionRate': 0.0,
                #     'interactions': 0
                # }
                
            except GoogleAdsException as ex:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt)  # exponential backoff
                time.sleep(delay)
                continue

    
    def getSummaryMetrics(self, user_id: str, customer_id: str) -> dict:
        try:
            # Convert user_id to ObjectId
            userId = ObjectId(user_id)
            
            # Get date ranges
            today = datetime.now()
            current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = current_month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            
            # Check if we have recent data in DB
            stored_metrics = mongo.db.SummaryPerformanceMetrics.find_one({
                'userId': userId,
                'customerId': customer_id,
                'updatedAt': {'$gte': current_month_start}
            })
            
            if stored_metrics:
                return {
                    'currentMonth': stored_metrics['currentMonth'],
                    'lastMonth': stored_metrics['lastMonth'],
                    'changes': stored_metrics['changes']
                }
                
            # If no recent data, fetch from Google Ads API
            client = self.agentService.getClient(user_id, customer_id)
            
            # Fetch metrics for both months
            current_metrics = self._fetchMonthMetrics(
                client, 
                customer_id,
                current_month_start,
                today
            )
            
            last_month_metrics = self._fetchMonthMetrics(
                client,
                customer_id,
                last_month_start,
                last_month_end
            )
            
            # Calculate changes
            changes = self._calculatePercentageChanges(current_metrics, last_month_metrics)
            
            # Prepare summary
            summary = {
                'currentMonth': current_metrics,
                'lastMonth': last_month_metrics,
                'changes': changes
            }
            
            # Store in database
            mongo.db.SummaryPerformanceMetrics.update_one(
                {
                    'userId': userId,
                    'customerId': customer_id,
                    'month': current_month_start
                },
                {
                    '$set': {
                        'currentMonth': current_metrics,
                        'lastMonth': last_month_metrics,
                        'changes': changes,
                        'updatedAt': datetime.utcnow()
                    }
                },
                upsert=True
            )
            
            return summary
            
        except Exception as e:
            print(f"Error getting summary metrics: {str(e)}")
            raise

    def _fetchMonthMetrics(self, client, customer_id: str, start_date: datetime, end_date: datetime) -> dict:
        try:
            ga_service = client.get_service("GoogleAdsService")
            
            query = """
                SELECT
                    metrics.cost_micros,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions,
                    metrics.average_cpc,
                    metrics.cost_per_conversion
                FROM campaign
                WHERE segments.date BETWEEN '%s' AND '%s'
            """ % (start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            
            response = ga_service.search(customer_id=customer_id, query=query)
            
            # Initialize metrics
            metrics = {
                'adSpend': 0.0,
                'impressions': 0,
                'clicks': 0,
                'conversions': 0,
                'averageCpc': 0.0,
                'cpa': 0.0
            }
            
            # Aggregate metrics across all campaigns
            for row in response:
                metrics['adSpend'] += row.metrics.cost_micros / 1_000_000
                metrics['impressions'] += row.metrics.impressions
                metrics['clicks'] += row.metrics.clicks
                metrics['conversions'] += row.metrics.conversions
                metrics['averageCpc'] = row.metrics.average_cpc / 1_000_000
                metrics['cpa'] = row.metrics.cost_per_conversion / 1_000_000 if row.metrics.conversions > 0 else 0
                
            return metrics
            
        except GoogleAdsException as ex:
            print(f"Google Ads API error: {ex}")
            raise

    def _calculatePercentageChanges(self, current: dict, previous: dict) -> dict:
        changes = {}
        
        for metric in current.keys():
            if previous[metric] != 0:
                percent_change = ((current[metric] - previous[metric]) / previous[metric]) * 100
                changes[metric] = round(percent_change, 2)
            else:
                changes[metric] = 100 if current[metric] > 0 else 0
                
        return changes