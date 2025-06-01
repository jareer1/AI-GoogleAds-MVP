from datetime import datetime
from ..database import mongo
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.chains import LLMChain
from bson import ObjectId
from ..config import AzureDeploymentName, AzureOpenAiVersion, AzureOpenAiKey, AzureOpenAiEndpoint
from  langchain_openai import AzureChatOpenAI
import json
from google.ads.googleads.client import GoogleAdsClient
from ..config import GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from google.protobuf import field_mask_pb2
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate
)
from .client import RestClient
import time



class AgentService:
    def __init__(self):
        # Use the chat‐based client instead of AzureOpenAI
        self.chat_llm = AzureChatOpenAI(
            deployment_name=AzureDeploymentName,     # your GPT-4o deployment name
            openai_api_version=AzureOpenAiVersion,
            openai_api_key=AzureOpenAiKey,
            azure_endpoint=AzureOpenAiEndpoint,
            temperature=0.0,
        )

 

        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                """
        You are a Google Ads keyword generation expert. Follow these strict rules:
        1. Respond ONLY with a list of keywords, one per line—no numbering, bullet points, or punctuation.
        2. Use only terms directly supported by the provided Business and Campaign Information.
        3. Do NOT invent products, features, or services not mentioned in the inputs.
        4. If the information is insufficient to generate any keywords, respond with EXACTLY:
        INSUFFICIENT_INFO
        5. Ensure all keywords are relevant to Google Ads best practices (e.g., use plausible search terms customers might use).
        """
            ),

            # Few-shot example to guide the model
            HumanMessagePromptTemplate.from_template(
                """
        Example:
        Business Information:
        A local bakery specializing in gluten-free pastries and artisan breads.

        Campaign Information:
        Launch campaign for new morning muffin selection featuring banana and blueberry.

        Generate relevant keyword ideas:
        """
            ),
            AIMessagePromptTemplate.from_template(
                """
        gluten-free banana muffins
        gluten-free blueberry muffins
        artisan banana muffins
        artisan blueberry muffins
        morning gluten-free pastries
        gluten-free breakfast muffins
        """
            ),

            # Actual user input
            HumanMessagePromptTemplate.from_template(
                """
        Business Information:
        {business_info}

        Campaign Information:
        {campaign_info}

        Generate relevant keyword ideas:
        """
            )
        ])


        self.chain = LLMChain(llm=self.chat_llm, prompt=self.prompt)

    def getCampaign(self, campaignId):
        return mongo.db.Campaigns.find_one({'_id': ObjectId(campaignId)})

    def getBusiness(self, userId):
        return mongo.db.Business.find_one({'userId': ObjectId(userId)})
    def getAdGroupIdByCampaignId(self, campaignId):
        ad_group = mongo.db.AdGroup.find_one({'campaignId': ObjectId(campaignId)})
        if not ad_group:
            raise Exception("No ad group found for this campaign")
        return str(ad_group['_id'])
    def getKeywords(self, campaign, business,adGroupId,checkWebsite,keywords):
        try:
            dataforSEO_keywords = self.get_dataforseo_keywords(business, campaign,checkWebsite,keywords)
            print('dataforSEO_keywords:', dataforSEO_keywords)
            business_info = (
                f"Business Name: {business['businessName']}\n"
                f"Category: {business['mainCategory']}\n"
                f"Suggested Keywords: {', '.join(dataforSEO_keywords)}"
            )
            campaign_info = (
                f"Target Audience: {campaign.get('targetAudience', 'Not specified')}"
            )

            result = self.chain.invoke({
                'business_info': business_info,
                'campaign_info': campaign_info
            })
            
            # Extract keywords from LLM response
            if isinstance(result, dict) and 'text' in result:
                keywords_text = result['text']
            else:
                keywords_text = result.content
                
            llm_keywords = [kw.strip() for kw in keywords_text.splitlines() if kw.strip()]
            
            # Get insights for the generated keywords
            keyword_insights = self.get_keyword_insights(
                keywords=llm_keywords,
                location=campaign.get('locationName', 'United States')
            )
            
            

            return keyword_insights, True

        except Exception as e:
            print(f"Error in getKeywords: {str(e)}")
            return str(e), False
    def saveKeywords(self, keyword_insights, adGroupId):
        try:
            result = mongo.db.AdGroup.update_one(
                {'_id': ObjectId(adGroupId)},
                {
                    '$set': {
                        'keywords': keyword_insights,
                        'keywordsUpdatedAt': datetime.utcnow()
                    }
                }
            )
            
            # Check if document was modified
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error saving keywords: {str(e)}")
            return False
    def getKeywordsFromDB(self, adGroupId):
        ad_group = mongo.db.AdGroup.find_one({'_id': ObjectId(adGroupId)})
        return ad_group.get('keywords') if ad_group else None



    def getAd(self, campaign, business, keywords):
        business_info = (
            f"Business Name: {business['businessName']}\n"
            f"Category: {business['mainCategory']}\n"
            f"Secondary Categories: {', '.join(business['secondaryCategories'])}\n"
            f"Service Areas: {', '.join(business['serviceAreas'])}"
        )
        campaign_info = (
            f"Target Audience: {campaign.get('targetAudience', 'Not specified')}"
        )
        keyword_strings = []
        for k in keywords:
            if isinstance(k, dict) and 'keyword' in k:
                keyword_strings.append(f"{k['keyword']}")

        keywords_info = "Keywords:\n" + "\n".join(keyword_strings)

        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("""
    You are an expert Google Ads copywriter. Generate a complete ad package in JSON format.
    The response must contain only a valid JSON object with exactly:
    - 5 headlines (max 30 chars each)
    - 5 descriptions (max 90 chars each)
    - 3 callouts (max 25 chars each)
    - 3 sitelinks (max 25 chars text, 35 chars descriptions)

    Example format:
    {{
        "headlines": ["Headline 1", "Headline 2", "Headline 3", "Headline 4", "Headline 5"],
        "descriptions": ["Description 1", "Description 2", "Description 3", "Description 4", "Description 5"],
        "callouts": [
            {{
                "text": "Callout text",
                "schedule": {{ "day_of_week": "MONDAY", "start_hour": 9, "end_hour": 17 }}
            }}
        ],
        "sitelinks": [
            {{
                "text": "Sitelink text",
                "final_url": "{{website_url}}",
                "description_1": "First description line",
                "description_2": "Second description line"
            }}
        ]
    }}
            """),
            HumanMessagePromptTemplate.from_template("""
    Create an ad using:

    Business Information:
    {business_info}

    Campaign Information:
    {campaign_info}

    Target Keywords:
    {keywords_info}
            """)
        ])

        ad_chain = LLMChain(llm=self.chat_llm, prompt=prompt)
        result = ad_chain.invoke({
            'business_info': business_info,
            'campaign_info': campaign_info,
            'keywords_info': keywords_info
        })
        print("LLM Response:", result)

        # Parse the LLM’s JSON output
        if isinstance(result, dict) and 'text' in result:
            json_str = result['text'].replace('```json\n', '').replace('\n```', '')
            ad_content = json.loads(json_str)
        else:
            ad_content = json.loads(result.content)

        print('adDocument is ', ad_content)
        ad_document = {
            'headlines': ad_content['headlines'],
            'descriptions': ad_content['descriptions'],
            'callouts': ad_content.get('callouts', []),
            'sitelinks': ad_content.get('sitelinks', []),
            'campaignId': str(campaign['_id']),
            'createdAt': datetime.utcnow(),
            'status': 'active',
            'published': False
        }

        return ad_document, True

    def saveAd(self, adDocument):
        try:
            # Convert campaignId from string to ObjectId
            if 'campaignId' in adDocument and isinstance(adDocument['campaignId'], str):
                adDocument['campaignId'] = ObjectId(adDocument['campaignId'])
                
            # Set timestamps
            adDocument['createdAt'] = datetime.utcnow()
            adDocument['status'] = 'active'
            adDocument['published'] = False
            
            # Insert the document
            result = mongo.db.Ads.insert_one(adDocument)
            
            # Verify insertion
            if result.inserted_id:
                print(f"Ad saved successfully with ID: {result.inserted_id}")
                return True
                
            return False
            
        except Exception as e:
            print(f"Error saving ad: {str(e)}")
            return False

    
    def getClient(self, userId,customerId):
        try:
            user = mongo.db.Users.find_one({'_id': ObjectId(userId)})
            if not user:
                raise Exception("User not found")
            
            if not user.get('refresh_token'):
                raise Exception("User missing required Google Ads credentials")

            print(f"Creating client for user: {user['email']}")
            
            # Build Google Ads client config - ensure all values are strings
            client_config = {
                "developer_token": str(GOOGLE_ADS_DEVELOPER_TOKEN),
                "client_id": str(GOOGLE_CLIENT_ID[0] if isinstance(GOOGLE_CLIENT_ID, tuple) else GOOGLE_CLIENT_ID),
                "client_secret": str(GOOGLE_CLIENT_SECRET),
                "refresh_token": str(user['refresh_token']),
                "login_customer_id": customerId,
                "use_proto_plus": True
            }
            
            print("Initializing Google Ads client with config:", client_config)
            client = GoogleAdsClient.load_from_dict(client_config)
            print("Google Ads client created successfully")
            
            return client

        except Exception as e:
            print(f"Error creating Google Ads client: {str(e)}")
            raise Exception("Google Ads authorization expired. Please reconnect your account.")
    def getCustomerId(self, campaignId):
        campaign = mongo.db.Campaigns.find_one({'_id': ObjectId(campaignId)})
        if not campaign or 'customerId' not in campaign:
            raise Exception("User not found or missing Google Ads customer ID")
        return campaign['customerId']
    def getCampaignByCampaignId(self, campaignId):

        campaign = mongo.db.Campaigns.find_one({'_id': ObjectId(campaignId)})
        if not campaign:
            raise Exception("No campaign found for this user")
        return campaign
    def score_keyword(self, item):
        try:
            # Get values with defaults of 0 if None
            sv = float(item.get("search_volume", 0) or 0)
            comp = float(item.get("competition_index", 0) or 0)
            cpc = float(item.get("cpc", 0) or 0)
            bid = float(item.get("high_top_of_page_bid", 0) or 0)
            
            # Ensure competition score is between 0-100
            comp_score = max(0, min(100 - comp, 100))

            # Calculate weighted score
            weighted_score = (
                (sv * 0.4) + 
                (comp_score * 0.2) + 
                (cpc * 0.2) + 
                (bid * 0.2)
            )
            
            return max(0, weighted_score)  # Ensure non-negative score
            
        except Exception as e:
            print(f"Error scoring keyword: {str(e)}")
            return 0  # Return default score on error
    def get_dataforseo_keywords(self,business,campaign,checkWebsite,keywords): 
        try:
            client = RestClient("admin@insightlytic.com", "258c3414aa949a09")

            if checkWebsite:
                website = business.get("websiteUrl", "").strip()
                if not website:
                    print("No website URL found in business data")
                    return []
                
                post_data = [{
                    "location_name": campaign.get("locationName"),
                    "target": website,
                    "language_name": "English",
                    "sort_by": "relevance"
                }]
                
                endpoint = "/v3/keywords_data/google_ads/keywords_for_site/live"

            else:
                if not keywords:
                    print("No keywords provided for keyword-based lookup")
                    return []
                
                post_data = [{
                    "location_name": campaign.get("locationName"),
                    "keywords": keywords,
                    "language_name": "English",
                    "sort_by": "relevance"
                }]
                
                endpoint = "/v3/keywords_data/google_ads/keywords_for_keywords/live"

            # Make the API call
            response = client.post(endpoint, post_data)
            tasks = response.get("tasks", [])
            if not tasks:
                print("No tasks returned from DataForSEO")
                return []
            
            results = tasks[0].get("result", [])
            
            # Score and sort
            scored = [
                (item, self.score_keyword(item))
                for item in results
                if isinstance(item, dict) and "keyword" in item
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            
            # Return top 50 keyword strings
            top_50 = [item["keyword"] for item, _ in scored[:50]]
            return top_50

        except Exception as e:
            print(f"Error fetching DataForSEO keywords: {e}")
            return []

    
    def get_keyword_insights(self, keywords: list, location: str) -> list:
        """Get specific keyword metrics from DataForSEO"""
        try:
            client = RestClient("admin@insightlytic.com", "258c3414aa949a09")
            
            # Prepare request payload
            post_data = [
                {
                    "keywords": keywords,
                    "location_name": location,
                    "language_name": "English"
                }
            ]
            print(f"Fetching keyword insights for {len(keywords)} keywords in {location}")

            # Make API call
            response = client.post("/v3/dataforseo_labs/google/keyword_overview/live", post_data)
            
            # Process response and extract specific metrics
            keyword_insights = []
            
            if response.get("status_code") == 20000:
                tasks = response.get("tasks", [])
                if tasks and "result" in tasks[0]:
                    for item in tasks[0]["result"][0].get("items", []):
                        keyword_info = item.get("keyword_info", {})
                        insight = {
                            "keyword": item.get("keyword"),
                            "competition_level": keyword_info.get("competition_level"),
                            "cpc": keyword_info.get("cpc"),
                            "search_volume": keyword_info.get("search_volume"),
                            "low_top_of_page_bid": keyword_info.get("low_top_of_page_bid"),
                            "high_top_of_page_bid": keyword_info.get("high_top_of_page_bid")
                        }
                        keyword_insights.append(insight)
            
            print(f"Retrieved insights for {len(keyword_insights)} keywords")
            return keyword_insights

        except Exception as e:
            print(f"Error getting keyword insights: {str(e)}")
            return []


    def createBudget(self,client, userId,campaignId):
        try:
            customer_id = self.getCustomerId(campaignId)            
            campaign = self.getCampaignByCampaignId(campaignId)            
            budget_service = client.get_service("CampaignBudgetService")            
            operation = client.get_type("CampaignBudgetOperation")
            budget = operation.create
            budget.name = f"Budget-{campaign['campaignName']}"
            budget.amount_micros = campaign['budget']  # $1 for testing
            budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
            response = budget_service.mutate_campaign_budgets(
                customer_id=customer_id,
                operations=[operation]
            )            
            budget_resource_name = response.results[0].resource_name
            mongo.db.Campaigns.update_one(
                {'_id': campaign['_id']},
                {
                    '$set': {
                        'budgetResourceName': budget_resource_name,
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            print('budget created successfuly')
            return budget_resource_name
            
        except Exception as e:
            print(f"Error creating budget: {str(e)}")
            raise
    def enable_campaign(self, client, userId,campaignId):
        try:
            customer_id = self.getCustomerId(campaignId)
            campaign = self.getCampaignByCampaignId(campaignId)
            
            if not campaign.get('resourceName'):
                raise Exception("Campaign resource name not found")

            campaign_service = client.get_service("CampaignService")
            operation = client.get_type("CampaignOperation")
            campaign_update = operation.update
            campaign_update.resource_name = campaign['resourceName']
            campaign_update.status = client.enums.CampaignStatusEnum.ENABLED

            mask = field_mask_pb2.FieldMask(paths=["status"])
            operation.update_mask.CopyFrom(mask)

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[operation],
            )

            mongo.db.Campaigns.update_one(
                {'_id': campaign['_id']},
                {
                    '$set': {
                        'status': 'ENABLED',
                        'updatedAt': datetime.utcnow()
                    }
                }
            )

            print(f"Campaign enabled successfully: {campaign['resourceName']}")
            return response

        except Exception as e:
            print(f"Error enabling campaign: {str(e)}")
            raise

    def createCampaign(self, client, userId,campaignId):
        try:
            customer_id = self.getCustomerId(campaignId)
            campaign = self.getCampaignByCampaignId(campaignId)
            
            if 'budgetResourceName' not in campaign:
                raise Exception("Campaign budget not created yet")
                
            campaign_service = client.get_service("CampaignService")
            
            # Create campaign operation
            operation = client.get_type("CampaignOperation")
            new_campaign = operation.create
            
            # Basic campaign settings
            new_campaign.name = campaign['campaignName']
            new_campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
            new_campaign.status = client.enums.CampaignStatusEnum.PAUSED  # Changed to PAUSED
            new_campaign.campaign_budget = campaign['budgetResourceName']

            # Set up bidding strategy
            new_campaign.target_spend = client.get_type("TargetSpend")
            new_campaign.target_spend.cpc_bid_ceiling_micros = 10000000  # $1.00 max CPC

            print(f"Creating campaign for customer ID: {customer_id}")
            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[operation]
            )
            
            campaign_resource_name = response.results[0].resource_name
            
            # Update MongoDB
            mongo.db.Campaigns.update_one(
                {'_id': campaign['_id']},
                {
                    '$set': {
                        'resourceName': campaign_resource_name,
                        'status': 'PAUSED',
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            
            print(f"Campaign created with resource name: {campaign_resource_name}")
            return campaign_resource_name
            
        except Exception as e:
            print(f"Error creating campaign: {str(e)}")
            raise
    def storeAdGroup(self, params):
        try:
            ad_group_document = {
                'name': params.get('name', 'Search Ad Group'),
                'campaignId': ObjectId(params['campaignId']),
                'type': params.get('type', 'SEARCH_STANDARD'),
                'cpcBidMicros': params.get('cpcBidMicros', 2000000),
                'status': 'PENDING',
                'createdAt': datetime.utcnow(),
            }
            
            result = mongo.db.AdGroup.insert_one(ad_group_document)
            return str(result.inserted_id)
        except Exception as e:
            print(f"Error storing ad group: {str(e)}")
            raise
    def createAdGroup(self, client, customer_id, campaign_resource_name, campaignId):
        try:
            # Get stored ad group details
            ad_group_data = mongo.db.AdGroup.find_one({
                'campaignId': ObjectId(campaignId),
                'status': 'PENDING'
            })
            
            if not ad_group_data:
                raise Exception("No pending ad group found for this campaign")

            # 1. Create the ad group first
            ad_group_service = client.get_service("AdGroupService")            
            operation = client.get_type("AdGroupOperation")
            ad_group = operation.create
            
            # Use stored parameters
            ad_group.name = ad_group_data['name']
            ad_group.campaign = campaign_resource_name
            ad_group.type_ = client.enums.AdGroupTypeEnum[ad_group_data['type']]
            ad_group.cpc_bid_micros = ad_group_data['cpcBidMicros']
            
            # Execute request
            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[operation]
            )
            
            ad_group_resource_name = response.results[0].resource_name

            # 2. Create keywords if they exist in the ad group
            if 'keywords' in ad_group_data and ad_group_data['keywords']:
                ad_group_criterion_service = client.get_service("AdGroupCriterionService")
                keyword_operations = []

                # Extract keyword text from keyword objects
                for keyword_obj in ad_group_data['keywords']:
                    if isinstance(keyword_obj, dict) and 'keyword' in keyword_obj:
                        operation = client.get_type("AdGroupCriterionOperation")
                        criterion = operation.create
                        criterion.ad_group = ad_group_resource_name
                        criterion.keyword.text = keyword_obj['keyword']  # Get keyword text from object
                        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD
                        keyword_operations.append(operation)
                    if keyword_operations:
                        keyword_response = ad_group_criterion_service.mutate_ad_group_criteria(
                            customer_id=customer_id,
                            operations=keyword_operations
                    )
                    
                    # Store keyword resource names
                    keyword_resource_names = [result.resource_name for result in keyword_response.results]
                    
                    # Update MongoDB with keyword status
                    mongo.db.AdGroup.update_one(
                        {'_id': ad_group_data['_id']},
                        {
                            '$set': {
                                'keywordResourceNames': keyword_resource_names,
                                'keywordsStatus': 'ACTIVE',
                                'keywordsUpdatedAt': datetime.utcnow()
                            }
                        }
                    )
            
            # 3. Update ad group status in MongoDB
            mongo.db.AdGroup.update_one(
                {'_id': ad_group_data['_id']},
                {
                    '$set': {
                        'resourceName': ad_group_resource_name,
                        'status': 'SUCCESS',
                        'completedAt': datetime.utcnow()
                    }
                }
            )
            
            return ad_group_resource_name

        except Exception as e:
            # Update status to FAILED if there's an error
            print(f"Error creating ad group: {str(e)}")
            raise
    def createResponsiveSearchAds(self, client, customer_id, ad_group_resource_name, campaignId,user_id):
        try:
            ads = self.getAdsByCampaignId(campaignId)
            if not ads:
                raise Exception("No unpublished ads found for this campaign")

            ad_service = client.get_service("AdGroupAdService")
            created_ads = []
            business=self.getBusiness(userId=user_id)
            for ad_content in ads:
                # Validate and fix URL first
                display_url = business['websiteUrl'].strip()
                if not display_url.startswith(('http://', 'https://')):
                    if display_url.startswith('www.'):
                        display_url = f'https://{display_url}'
                    else:
                        display_url = f'https://www.{display_url}'
                
                # Create operation
                operation = client.get_type("AdGroupAdOperation")
                ad_group_ad = operation.create
                ad_group_ad.ad_group = ad_group_resource_name
                ad = client.get_type("Ad")

                # Process headlines - ensure they meet length requirements
                headlines = []
                for headline in ad_content['headlines'][:15]:  # Max 15 headlines
                    # Clean and truncate headline
                    cleaned_headline = headline.strip()
                    if len(cleaned_headline) > 30:
                        cleaned_headline = cleaned_headline[:27] + "..."
                    headlines.append(cleaned_headline)
                    
                    headline_asset = client.get_type("AdTextAsset")
                    headline_asset.text = cleaned_headline
                    ad.responsive_search_ad.headlines.append(headline_asset)

                # Process descriptions - ensure they meet length requirements
                descriptions = []
                for description in ad_content['descriptions'][:4]:  # Max 4 descriptions
                    cleaned_desc = description.strip()
                    if len(cleaned_desc) > 90:
                        cleaned_desc = cleaned_desc[:87] + "..."
                    descriptions.append(cleaned_desc)
                    
                    desc_asset = client.get_type("AdTextAsset")
                    desc_asset.text = cleaned_desc
                    ad.responsive_search_ad.descriptions.append(desc_asset)

                # Set final URL
                ad.final_urls.append(display_url)
                ad_group_ad.ad = ad

                # Debug logging
                print(f"Creating ad with:")
                print(f"- URL: {display_url}")
                print(f"- Headlines: {headlines}")
                print(f"- Description lengths: {[len(d) for d in descriptions]}")

                # Execute request
                response = ad_service.mutate_ad_group_ads(
                    customer_id=customer_id,
                    operations=[operation]
                )

                # Store successful ad and mark as published
                mongo.db.Ads.update_one(
                    {'_id': ad_content['_id']},
                    {
                        '$set': {
                            'published': True,
                            'publishedAt': datetime.utcnow(),
                            'adResourceName': response.results[0].resource_name,
                            'final_url': display_url,
                            'published_headlines': headlines,  # Store the actual published headlines
                            'published_descriptions': descriptions  # Store the actual published descriptions
                        }
                    }
                )

                created_ads.append(response.results[0].resource_name)

            return created_ads

        except Exception as e:
            print(f"Error creating responsive search ads: {str(e)}")
            raise
    
    def getAdsByCampaignId(self, campaignId):
        try:
            ads = mongo.db.Ads.find({
                'campaignId': ObjectId(campaignId),
                'status': 'active',
                'published': {'$ne': True}  # Only get unpublished ads
            })
            return list(ads)
        except Exception as e:
            print(f"Error getting ads: {str(e)}")
            
    def disable_campaign(self, client, userId, campaignId):
        try:
            customer_id = self.getCustomerId(campaignId)
            campaign = self.getCampaignByCampaignId(campaignId)
            
            if not campaign.get('resourceName'):
                raise Exception("Campaign resource name not found")

            campaign_service = client.get_service("CampaignService")
            operation = client.get_type("CampaignOperation")
            campaign_update = operation.update
            campaign_update.resource_name = campaign['resourceName']
            campaign_update.status = client.enums.CampaignStatusEnum.PAUSED

            mask = field_mask_pb2.FieldMask(paths=["status"])
            operation.update_mask.CopyFrom(mask)

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[operation],
            )

            # Update campaign status in MongoDB
            mongo.db.Campaigns.update_one(
                {'_id': campaign['_id']},
                {
                    '$set': {
                        'status': 'PAUSED',
                        'updatedAt': datetime.utcnow()
                    }
                }
            )

            print(f"Campaign disabled successfully: {campaign['resourceName']}")
            return response

        except Exception as e:
            print(f"Error disabling campaign: {str(e)}")
            raise