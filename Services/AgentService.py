from datetime import datetime
from ..database import mongo
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.chains import LLMChain
from bson import ObjectId
from ..config import AzureDeploymentName, AzureOpenAiVersion, AzureOpenAiKey, AzureOpenAiEndpoint
from  langchain_openai import AzureChatOpenAI
import json

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

    def getKeywords(self, campaign, business):
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

            keyword_document = {
            'keywords': keywords,
            'campaignId': campaign['_id'],
            'createdAt': datetime.utcnow(),
            'status': 'active'
        }

            # Insert single document with all keywords
            mongo.db.Keywords.insert_one(keyword_document)


            return keywords, True

        except Exception as e:
            return str(e), False
    def getKeywordsFromDB(self, campaignId):
        return mongo.db.Keywords.find_one({'campaignId': ObjectId(campaignId)})
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
        keywords_info = "Keywords: " + ", ".join(keywords['keywords'])

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
            