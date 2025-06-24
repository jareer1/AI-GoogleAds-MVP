from flask import Blueprint, request, jsonify, redirect
from marshmallow import ValidationError
from ..Models.Request.User.UserCreateReqVM import UserSignupReqVM
from ..Services.UserService import UserService
from ..config import frontendUrl
class UserController:
    def __init__(self, user_service: UserService):
        self.userBluePrint = Blueprint('user', __name__)
        self.userService = user_service
        self.setup_routes()
        
    def setup_routes(self):
        self.userBluePrint.route('/connect-with-google', methods=['POST'])(self.connectWithGoogle)
        self.userBluePrint.route('/oauth2callback')(self.oauth2callback)
        self.userBluePrint.route('/signup',methods=['POST'])(self.signup)
        self.userBluePrint.route('/login', methods=['POST'])(self.login)
        self.userBluePrint.route('/customerIds/<userId>', methods=['GET'])(self.getCustomerIds)  # Reusing signup for user creation
    def signup(self):
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            try:
                schema = UserSignupReqVM()
                validated_data = schema.load(data)
            except ValidationError as e:
                return jsonify({'message':"Bad Request"}), 400
            # Call service to create user
            user_id, user_email,token = self.userService.createUser(
                email=validated_data['email'],
                password=validated_data['password']
            )

            return jsonify({
                'userId': str(user_id),
                'userEmail': user_email,
                'token': token
            }), 201

        except Exception as e:
            print(f"Error in signup: {str(e)}")
            return jsonify({'error': str(e)}), 500        
    
    def login(self):
        try:
            data = request.get_json()
           
            try:
                schema = UserSignupReqVM()
                validated_data = schema.load(data)
            except ValidationError as e:
                return jsonify({'message':"Bad Request"}), 400
            # Call service to verify credentials
            user_id, user_email,token = self.userService.login(
                email=validated_data['email'],
                password=validated_data['password']
            )

            return jsonify({
                'userId': str(user_id),
                'userEmail': user_email,
                'token': token
            }), 200

        except Exception as e:
            print(f"Error in login: {str(e)}")
            return jsonify({'error': str(e)}), 401
    def connectWithGoogle(self):
        try:
            # Validate request data
            signup_data = request.get_json()
            if not signup_data:
                return jsonify({'error': 'No data provided'}), 400
                
            redirect_url, error = self.userService.initiate_oauth(signup_data['email'])
            
            if error:
                return jsonify({'error': error}), 400
                
            # Redirect to Google OAuth consent screen
            print('redicted_url:', redirect_url)
            return redirect(redirect_url)
            
        except ValidationError as e:
            return jsonify({'error': e.messages}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    def oauth2callback(self):
        try:
            # Handle OAuth callback
            state = request.args.get('state')
            code = request.args.get('code')
            
            if not state or not code:
                return jsonify({'error': 'Missing state or code'}), 400
                
            result, success,email = self.userService.handle_oauth_callback(state, code)
            print('success:', success)
            if not success:
                return jsonify({'error': result}), 400
            customers = self.userService.get_customer_ids(email)
            customer_ids_param = ','.join(customers)

            redirect_url = f'{frontendUrl}/dashboard/google-ads-callback?customerIds={customer_ids_param}'
            print('redirect_url:', redirect_url)
            return redirect({"redirect_url":redirect_url})

            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    def getCustomerIds(self, userId):
        try:
            # Get customer IDs for the user
            customer_ids = self.userService.getCustomerIdsFromDB(userId)
            if not customer_ids:
                return jsonify({'message': 'No customer IDs found'}), 404
            
            return jsonify({'customerIds': customer_ids}), 200
            
        except Exception as e:
            print(f"Error fetching customer IDs: {str(e)}")
            return jsonify({'error': str(e)}), 500
        