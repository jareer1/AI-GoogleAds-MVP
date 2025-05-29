import os
env = os.environ.get('_ENV')
DB_USERNAME ='jareer'
DB_PASSWORD = 'jareer'
cluster_url = "ai-agent-google.mpscqje.mongodb.net"
db_name = 'Development'
MONGO_URI = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{cluster_url}/{db_name}?retryWrites=true&w=majority&tls=true"
AzureOpenAiEndpoint = "https://cognidata.openai.azure.com/"
AzureOpenAiKey = "3sXbp2pMR6wgu0hCGxQHoxB4uADGpGtYBycbYH30jswvjBaFcvoLJQQJ99AKACYeBjFXJ3w3AAABACOG8T9Y"
AzureOpenAiVersion = "2024-08-01-preview"
AzureDeploymentName='cognidata-gpt-4o'    
GOOGLE_ADS_DEVELOPER_TOKEN= "s4qUCowkrWMdtTA9-tkxSA"
GOOGLE_CLIENT_ID="310654508589-d1vm4tkv14rs3i0doh594r7209tgmc93.apps.googleusercontent.com",
GOOGLE_CLIENT_SECRET="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"
env='dev'
if env=='dev':
    frontendUrl = "http://localhost:5000/user/oauth2callback"
