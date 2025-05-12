from datetime import datetime
from ..database import mongo
from bson import ObjectId
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from werkzeug.security import generate_password_hash
from datetime import datetime
from bson import ObjectId
from werkzeug.security import check_password_hash


from google_auth_oauthlib.flow import Flow
import secrets
import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from ..config import GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
class UserService:
    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.client_secrets_file = os.path.join(current_dir, "client_secret.json")
        
        self.scopes = ["https://www.googleapis.com/auth/adwords"]
        self.redirect_uri = "http://localhost:8080/oauth2callback"
    

    def createUser(self, email: str, password: str) -> tuple[ObjectId, str]:
        """Create a new user with hashed password"""
        try:
            # Check if user already exists
            if mongo.db.Users.find_one({'email': email}):
                raise Exception('User already exists')

            # Hash password
            hashed_password = generate_password_hash(
                password,
                method='pbkdf2:sha256',
                salt_length=8
            )

            # Create user document
            user = {
                'email': email,
                'password': hashed_password,
                'createdAt': datetime.utcnow(),
                'updatedAt': datetime.utcnow()
            }

            # Insert into database
            result = mongo.db.Users.insert_one(user)
            
            return result.inserted_id, email

        except Exception as e:
            print(f"Error creating user: {str(e)}")
            raise
    def login(self, email: str, password: str) -> tuple[str, str]:
        """Verify user credentials and return user info"""
        try:
            # Find user by email
            user = mongo.db.Users.find_one({'email': email})
            if not user:
                raise Exception('User not found')

            # Verify password
            if not check_password_hash(user['password'], password):
                raise Exception('Invalid password')

            # Update last login timestamp
            mongo.db.Users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'lastLoginAt': datetime.utcnow(),
                        'updatedAt': datetime.utcnow()
                    }
                }
            )

            return user['_id'], user['email']

        except Exception as e:
            print(f"Error in login: {str(e)}")
            raise    
    def initiate_oauth(self, email):
        try:
            # Check if user exists with refresh token
            existing_user = mongo.db.Users.find_one({
                'email': email,
                'refresh_token': {'$exists': True}
            })
            print(f"Existing user: {existing_user}")
            
            if existing_user and existing_user.get('refresh_token'):
                return None, "User already authenticated"
                
            # Create or update user
            state = secrets.token_urlsafe(32)
            user_data = {
                'email': email,
                'oauth_state': state,
                'updatedAt': datetime.utcnow()
            }
            

            mongo.db.Users.update_one(
                {'email': email},
                {'$set': user_data}
            )
                
            # Initialize OAuth flow with prompt parameter
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            # Add prompt='consent' to force the consent screen
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',  # Force consent screen to get refresh token
                state=state
            )
            
            return auth_url, None
        
        except Exception as e:
            print(f"OAuth initiation error: {str(e)}")  # Debug logging
            return None, str(e)
            
    def handle_oauth_callback(self, state, code):
        """Handle OAuth callback and store tokens"""
        try:
            # Verify state and get user
            user = mongo.db.Users.find_one({'oauth_state': state})
            if not user:
                return "Invalid state parameter", False
            print('user for which validating state:', user)
            # Initialize flow
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.scopes,
                redirect_uri=self.redirect_uri,
                state=state
            )
            
            # Exchange code for tokens
            flow.fetch_token(code=code)
            credentials = flow.credentials
            if not credentials.refresh_token:
                return "No refresh token received from Google", False,None
        
            
            # Update user with tokens
            mongo.db.Users.update_one(
                {'_id': user['_id']},
                {
                    '$set': {
                        'refresh_token': credentials.refresh_token,
                        'access_token': credentials.token,
                        'token_expiry': credentials.expiry,
                        'oauth_state': None,
                        'updatedAt': datetime.utcnow()
                    }
                }
            )
            
            return "Authentication successful", True,user['email']
            
        except Exception as e:
            return str(e), False, None
    
    # def get_customer_names(self, client, customer_ids: list[str]) -> list[dict]:
    #     """Get customer names using Google Ads Query"""
    #     try:
    #         ga_service = client.get_service("GoogleAdsService")
    #         customers = []

    #         for customer_id in customer_ids:
    #             # Create query to get customer details
    #             query = """
    #                 SELECT 
    #                     customer.id,
    #                     customer.descriptive_name
    #                 FROM customer
    #                 WHERE customer.id = '%s'
    #             """ % customer_id

    #             # Execute the search request
    #             response = ga_service.search(
    #                 customer_id=customer_id,
    #                 query=query
    #             )

    #             # Process the response
    #             for row in response:
    #                 customers.append({
    #                     'id': str(row.customer.id),
    #                     'name': row.customer.descriptive_name
    #                 })

    #         return customers

    #     except Exception as e:
    #         print(f"Error getting customer names: {str(e)}")
    #         raise
    def get_customer_ids(self, email: str) -> list[str]:
        try:
            # 1. Get user and verify refresh token
            user = mongo.db.Users.find_one({'email': email})
            if not user or 'refresh_token' not in user:
                raise Exception("User not authenticated")
            print('user:', user)
            # 2. Load OAuth client config from file
            flow = Flow.from_client_secrets_file(
                self.client_secrets_file,
                scopes=self.scopes
            )

            # 3. Refresh the access token
            request = Request()
            creds = Credentials(
                token=None,
                refresh_token=user['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=flow.client_config['client_id'],
                client_secret=flow.client_config['client_secret'],
                scopes=self.scopes
            )
            
            print("Refreshing token...")
            creds.refresh(request)
            print("Token refreshed successfully")

            # 4. Create Google Ads client config
            google_ads_config = {
                "developer_token": GOOGLE_ADS_DEVELOPER_TOKEN,
                "use_proto_plus": True,
                "client_id": flow.client_config['client_id'],
                "client_secret": flow.client_config['client_secret'],
                "refresh_token": user['refresh_token'],
                "login_customer_id": None
            }
            print("Google Ads config:", google_ads_config)

            # 5. Create client and get customer service
            client = GoogleAdsClient.load_from_dict(google_ads_config)
            customer_service = client.get_service("CustomerService")
            response = customer_service.list_accessible_customers()
            customer_ids = [resource_name.split('/')[1] for resource_name in response.resource_names]
            print("Customer IDs:", customer_ids)
            # customers = self.get_customer_names(client, customer_ids)
            
                
            return customer_ids
            

        except Exception as e:
            print(f"Error in get_customer_ids: {str(e)}")
            raise