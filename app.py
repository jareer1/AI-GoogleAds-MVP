# app.py - Main application file
import json
import logging
from flask import Flask, jsonify, request, make_response, render_template
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_babel import Babel
import traceback
from .Services.AgentService import AgentService
from .Controller.AgentController import AgentController
# Import services and controllers
from .Services.CampaignService import CampaignService
from .Controller.CampaignController import CampaignController
from .database import init_mongodb
from .Controller.BusinessController import BusinessController
from .Services.BusinessService import BusinessService
from .Services.UserService import UserService
from .Controller.UserController import UserController
from .Controller.DashboardController import DashboardController
from .Services.DashboardService import DashboardService
# Configure logging
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='templates')
app.config['SESSION_TYPE'] = 'filesystem'
app.config["SESSION_PERMANENT"] = False

# Apply CORS and proxy fix
CORS(
    app,
    resources={r"/*": {"origins": "*"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Initialize database
init_mongodb(app)

# Initialize babel
babel = Babel(app)
babel.init_app(app)

# Initialize services
campaignService = CampaignService()

campaignController = CampaignController(campaignService)
app.register_blueprint(campaignController.campaignBluePrint)

businessService = BusinessService()
businessController=BusinessController(businessService)

app.register_blueprint(businessController.businessBluePrint)

agentService = AgentService()
agentController=AgentController(agentService)
app.register_blueprint(agentController.agentBluePrint)


user_service = UserService()
user_controller = UserController(user_service)

app.register_blueprint(user_controller.userBluePrint)

dashboardService = DashboardService(agentService)
dashboardController = DashboardController(dashboardService)
app.register_blueprint(dashboardController.dashboardBluePrint)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)