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

        # Wrap your template in a ChatPromptTemplate
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                "You are a keyword generator for Google Ads. Respond ONLY with keywords, one per line. No additional text, explanations, or formatting."
            ),
            HumanMessagePromptTemplate.from_template(
                """Based on this information, generate relevant keywords:

                Business Information:
                {business_info}

                Campaign Information:
                {campaign_info}
                """
            )
        ])

        self.chain = LLMChain(llm=self.chat_llm, prompt=self.prompt)

    def getCampaign(self, campaignId):
        return mongo.db.Campaigns.find_one({'_id': ObjectId(campaignId)})

    def getBusiness(self, campaignId):
        return mongo.db.Business.find_one({'campaignId': ObjectId(campaignId)})
    def getAdGroupIdByCampaignId(self, campaignId):
        ad_group = mongo.db.AdGroup.find_one({'campaignId': ObjectId(campaignId)})
        if not ad_group:
            raise Exception("No ad group found for this campaign")
        return str(ad_group['_id'])
    def getKeywords(self, campaign, business,adGroupId):
        try:
            business_info = (
                f"Business Name: {business['businessName']}\n"
                f"Category: {business['mainCategory']}\n"
                f"Secondary Categories: {', '.join(business['secondaryCategories'])}\n"
                f"Service Areas: {', '.join(business['serviceAreas'])}"
            )
            campaign_info = (
                f"Campaign Focus: {campaign['campaignFocus']}\n"
                f"Target Audience: {campaign.get('targetAudience', 'Not specified')}"
            )
            print("Business Info:", business_info)

            # This now calls the chat completions endpoint under the hood
            result = self.chain.invoke({
                'business_info': business_info,
                'campaign_info': campaign_info
            })
            print("LLM Response:", result)
            if isinstance(result, dict) and 'text' in result:
                keywords_text = result['text']
            else:
                keywords_text = result.content
            keywords = [kw.strip() for kw in keywords_text.splitlines() if kw.strip()]

            mongo.db.AdGroup.update_one(
                {'_id': ObjectId(adGroupId)},
                {
                    '$set': {
                        'keywords': keywords,
                        'keywordsUpdatedAt': datetime.utcnow()
                    }
                }
            )



            return keywords, True

        except Exception as e:
            return str(e), False
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
            f"Campaign Focus: {campaign['campaignFocus']}\n"
            f"Target Audience: {campaign.get('targetAudience', 'Not specified')}"
        )
        keywords_info = "Keywords: " + ", ".join(keywords)

        # Escape the JSON braces by doubling them:
        system_message = """You are an ad copy generator for Google Ads. Generate a compelling ad in JSON format. Do not include any additional text or explanations. Only return a valid JSON object with this exact structure: {{  
        "headlines": ["Headline 1", "Headline 2", "Headline 3"],  
        "descriptions": ["Description Line 1", "Description Line 2"],  
        "displayUrl": "www.example.com",  
        "callToAction": "Call to action phrase"  
        }}"""

        human_message = """Generate an ad based on:

    Business Information:
    {business_info}

    Campaign Information:
    {campaign_info}

    Target Keywords:
    {keywords_info}"""

        ad_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_message),
            HumanMessagePromptTemplate.from_template(human_message)
        ])

        ad_chain = LLMChain(llm=self.chat_llm, prompt=ad_prompt)
        result = ad_chain.invoke({
            'business_info': business_info,
            'campaign_info': campaign_info,
            'keywords_info': keywords_info
        })
        print("LLM Response:", result)
        if isinstance(result, dict) and 'text' in result:
            json_str = result['text'].replace('```json\n', '').replace('\n```', '')
            ad_content = json.loads(json_str)
        else:
            ad_content = json.loads(result.content)

        ad_document = {
            'headlines': ad_content['headlines'],
            'descriptions': ad_content['descriptions'],
            'displayUrl': ad_content['displayUrl'],
            'callToAction': ad_content['callToAction'],
            'campaignId': campaign['_id'],
            'createdAt': datetime.utcnow(),
            'status': 'active'
        }

        # Store in MongoDB Ads collection
        mongo.db.Ads.insert_one(ad_document)
    
        return ad_content, True
    
    def getClient(self, userId: str):
        try:
            user = mongo.db.Users.find_one({'_id': ObjectId(userId)})
            if not user:
                raise Exception("User not found")
            
            if not user.get('refresh_token') or not user.get('google_ads_customer_id'):
                raise Exception("User missing required Google Ads credentials")

            print(f"Creating client for user: {user['email']}")
            
            # Build Google Ads client config - ensure all values are strings
            client_config = {
                "developer_token": str(GOOGLE_ADS_DEVELOPER_TOKEN),
                "client_id": str(GOOGLE_CLIENT_ID[0] if isinstance(GOOGLE_CLIENT_ID, tuple) else GOOGLE_CLIENT_ID),
                "client_secret": str(GOOGLE_CLIENT_SECRET),
                "refresh_token": str(user['refresh_token']),
                "login_customer_id": str(user['google_ads_customer_id']),
                "use_proto_plus": True
            }
            
            print("Initializing Google Ads client with config:", client_config)
            client = GoogleAdsClient.load_from_dict(client_config)
            print("Google Ads client created successfully")
            
            return client

        except Exception as e:
            print(f"Error creating Google Ads client: {str(e)}")
            raise
    def getCustomerId(self, userId):
        user = mongo.db.Users.find_one({'_id': ObjectId(userId)})
        if not user or 'google_ads_customer_id' not in user:
            raise Exception("User not found or missing Google Ads customer ID")
        return user['google_ads_customer_id']
    def getCampaignByCampaignId(self, campaignId):

        campaign = mongo.db.Campaigns.find_one({'_id': ObjectId(campaignId)})
        if not campaign:
            raise Exception("No campaign found for this user")
        return campaign
    
    def createBudget(self,client, userId,campaignId):
        try:
            customer_id = self.getCustomerId(userId)            
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
            customer_id = self.getCustomerId(userId)
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
            customer_id = self.getCustomerId(userId)
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

                for keyword in ad_group_data['keywords']:
                    operation = client.get_type("AdGroupCriterionOperation")
                    criterion = operation.create
                    criterion.ad_group = ad_group_resource_name
                    criterion.keyword.text = keyword
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
            if 'ad_group_data' in locals() and ad_group_data:
                mongo.db.AdGroup.update_one(
                    {'_id': ad_group_data['_id']},
                    {
                        '$set': {
                            'status': 'FAILED',
                            'error': str(e),
                            'completedAt': datetime.utcnow()
                        }
                    }
                )
            print(f"Error creating ad group: {str(e)}")
            raise
    def createResponsiveSearchAds(self, client, customer_id, ad_group_resource_name, campaignId):
        try:
            ads = self.getAdsByCampaignId(campaignId)
            if not ads:
                raise Exception("No unpublished ads found for this campaign")

            ad_service = client.get_service("AdGroupAdService")
            created_ads = []

            for ad_content in ads:
                # Validate and fix URL first
                display_url = ad_content['displayUrl'].strip()
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
            customer_id = self.getCustomerId(userId)
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