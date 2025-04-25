from flask import Flask, request, jsonify
import logging
import os
from flask_cors import CORS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS
CORS(app)

# Load configuration
def get_settings():
    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "google_ads_developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
    }

@app.before_first_request
def before_first_request():
    """Run before the first request is processed"""
    logger.info("Starting Google Ads AI Agent application")
    settings = get_settings()
    logger.info(f"Environment: {settings['environment']}")
    
    # Validate required settings
    if not settings.get("openai_api_key"):
        logger.warning("OpenAI API key not found in environment variables")




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)