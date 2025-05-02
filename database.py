from flask_pymongo import PyMongo
from .config import MONGO_URI

# make mongo as global
mongo = PyMongo()

# Create function to initialize the mongodb
def init_mongodb(app):
    app.config['MONGO_URI'] = MONGO_URI
    mongo.init_app(app)