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
        
    def getCampaignMetrics(self, user_id: str) -> List[Dict]:
        try:
            # Get all campaigns for user
            campaigns = self.getUserCampaigns(user_id)
            if not campaigns:
                return []
                
            metrics = []
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            for campaign in campaigns:
                    # Check for existing metrics
                    stored_metrics = self.getStoredMetrics(campaign['_id'], yesterday)
                    
                    if stored_metrics:
                        metrics.append({
                            'campaignId': str(campaign['_id']),
                            'campaignName': campaign['campaignName'],
                            **stored_metrics
                        })
                    else:
                        # Fetch fresh metrics from Google Ads
                        fresh_metrics = self.fetchGoogleAdsMetrics(
                            user_id, 
                            campaign['resourceName']
                        )
                        
                        # Store new metrics
                        self.storeMetrics(campaign['_id'], fresh_metrics)
                        
                        metrics.append({
                            'campaignId': str(campaign['_id']),
                            'campaignName': campaign['campaignName'],
                            **fresh_metrics
                        })
                        
                
                    
            return metrics
            
        except Exception as e:
            print(f"Error processing campaign {campaign['_id']}: {str(e)}")
            raise Exception(f"Error processing campaign {campaign['_id']}: {str(e)}")
                    
            
    def getUserCampaigns(self, user_id: str):
        return list(mongo.db.Campaigns.find({'userId': ObjectId(user_id)}))
        
    def getStoredMetrics(self, campaign_id: ObjectId, since_date: datetime):
    # Ensure since_date is at midnight for proper comparison
        since_date = since_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        metrics = mongo.db.PerformanceMetrics.find_one({
            'campaignId': campaign_id,
            'date': {'$gte': since_date}
        })
        if metrics:
            return {
                'clicks': metrics['clicks'],
                'event': metrics['event'],
                'ctr': metrics['ctr'],
                'conversions': metrics['conversions']
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
            
    def fetchGoogleAdsMetrics(self, user_id: str, campaign_resource_name: str) -> Dict:
        max_retries = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                client = self.agentService.getClient(user_id)
                customer_id = self.agentService.getCustomerId(user_id)
                
                ga_service = client.get_service("GoogleAdsService")
                
                query = """
                    SELECT 
                        campaign.id,
                        metrics.clicks,
                        metrics.interactions,
                        metrics.ctr,
                        metrics.conversions
                    FROM campaign
                    WHERE campaign.resource_name = '%s'
                    AND segments.date DURING LAST_7_DAYS
                """ % campaign_resource_name
                
                response = ga_service.search(
                    customer_id=customer_id,
                    query=query
                )
                print('response is:', response)
                # Process the first row (should only be one)
                for row in response:
                    return {
                        'clicks': row.metrics.clicks,
                        'event': row.metrics.interactions,
                        'ctr': float(row.metrics.ctr),
                        'conversions': row.metrics.conversions
                    }
                    
                return {
                    'clicks': 0,
                    'event': 0,
                    'ctr': 0.0,
                    'conversions': 0
                }
                
            except GoogleAdsException as ex:
                if attempt == max_retries - 1:
                    raise
                    
                delay = base_delay * (2 ** attempt)  # exponential backoff
                time.sleep(delay)
                continue
    def getSummaryMetrics(self, user_id: str, start_date: datetime, end_date: datetime, compare: bool) -> Dict:
        try:
            # Check cache first
            cached_metrics = self.getCachedSummary(user_id, start_date, end_date)
            if cached_metrics:
                return cached_metrics
            
            # Get fresh metrics from Google Ads
            client = self.agentService.getClient(user_id)
            customer_id = self.agentService.getCustomerId(user_id)
            
            # Get current period metrics
            current_metrics = self.fetchGoogleAdsTotals(
                client,
                customer_id,
                start_date,
                end_date
            )
            
            # Get comparison metrics if requested
            deltas = {}
            if compare:
                period_length = (end_date - start_date).days
                prior_end = start_date - timedelta(days=1)
                prior_start = prior_end - timedelta(days=period_length)
                
                prior_metrics = self.fetchGoogleAdsTotals(
                    client,
                    customer_id,
                    prior_start,
                    prior_end
                )
                
                # Calculate deltas
                deltas = self.calculateDeltas(current_metrics, prior_metrics)
            
            # Get daily traffic data
            daily_traffic = self.fetchDailyTraffic(
                client,
                customer_id,
                start_date,
                end_date
            )
            
            # Prepare result
            result = {
                'totals': current_metrics,
                'deltas': deltas,
                'dailyTraffic': daily_traffic
            }
            
            # Cache the results
            self.cacheSummaryMetrics(
                user_id,
                start_date,
                end_date,
                result
            )
            
            return result
            
        except Exception as e:
            print(f"Error getting summary metrics: {str(e)}")
            raise
    
    def getCachedSummary(self, user_id: str, start_date: datetime, end_date: datetime) -> Dict:
        cache_ttl = datetime.utcnow() - timedelta(days=1)
        
        cached = mongo.db.SummaryPerformanceMetrics.find_one({
            'userId': ObjectId(user_id),
            'startDate': start_date,
            'endDate': end_date,
            'lastUpdated': {'$gte': cache_ttl}
        })
        
        if cached:
            return {
                'totals': cached['totals'],
                'deltas': cached.get('deltas', {}),
                'dailyTraffic': cached['dailyTraffic']
            }
        return None
    
    def cacheSummaryMetrics(self, user_id: str, start_date: datetime, end_date: datetime, metrics: Dict):
        mongo.db.SummaryPerformanceMetrics.update_one(
            {
                'userId': ObjectId(user_id),
                'startDate': start_date,
                'endDate': end_date
            },
            {
                '$set': {
                    **metrics,
                    'lastUpdated': datetime.utcnow()
                }
            },
            upsert=True
        )
    
    def fetchGoogleAdsTotals(self, client, customer_id: str, start_date: datetime, end_date: datetime) -> Dict:
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT
                metrics.cost_micros,
                metrics.clicks,
                metrics.conversions,
                metrics.average_cpc,
                metrics.cost_per_conversion
            FROM campaign
            WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' 
                AND '{end_date.strftime('%Y-%m-%d')}'
        """
        
        response = ga_service.search(customer_id=customer_id, query=query)
        
        totals = {
            'spend': 0.0,
            'clicks': 0,
            'conversions': 0,
            'avgCpc': 0.0,
            'cpa': 0.0
        }
        
        for row in response:
            totals['spend'] += row.metrics.cost_micros / 1_000_000
            totals['clicks'] += row.metrics.clicks
            totals['conversions'] += row.metrics.conversions
            totals['avgCpc'] = row.metrics.average_cpc / 1_000_000
            totals['cpa'] = row.metrics.cost_per_conversion / 1_000_000
        
        return totals
    
    def calculateDeltas(self, current: Dict, prior: Dict) -> Dict:
        deltas = {}
        for key in current.keys():
            if prior[key] != 0:
                deltas[key] = round((current[key] - prior[key]) / prior[key] * 100, 1)
            else:
                deltas[key] = 100 if current[key] > 0 else 0
        return deltas
    
    def fetchDailyTraffic(self, client, customer_id: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        ga_service = client.get_service("GoogleAdsService")
        
        query = f"""
            SELECT
                segments.date,
                metrics.clicks
            FROM campaign
            WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' 
                AND '{end_date.strftime('%Y-%m-%d')}'
        """
        
        response = ga_service.search(customer_id=customer_id, query=query)
        
        daily_traffic = []
        for row in response:
            daily_traffic.append({
                'date': row.segments.date,
                'clicks': row.metrics.clicks
            })
        
        return sorted(daily_traffic, key=lambda x: x['date'])