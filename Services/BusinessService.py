from datetime import datetime
from ..database import mongo

class BusinessService:
    def create(self, business_data):
        """Create a new business entry"""
        try:
            # Add metadata
            business_data['createdAt'] = datetime.utcnow()
            business_data['updatedAt'] = datetime.utcnow()
            
            # Set default values for optional fields
            business_data.setdefault('secondaryCategories', [])
            business_data.setdefault('serviceAreas', [])
            
            # Insert into database
            result = mongo.db.Business.insert_one(business_data)
            
            return {
                'message': 'Business created successfully',
                'businessId': str(result.inserted_id)
            }, True
            
        except Exception as e:
            return str(e), False