import os
DB_USERNAME ='jareer'
DB_PASSWORD = 'jareer'
cluster_url = "ai-agent-google.mpscqje.mongodb.net"
db_name = 'Development'
MONGO_URI = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{cluster_url}/{db_name}?retryWrites=true&w=majority&tls=true"
AzureOpenAiEndpoint = "https://cognidata.openai.azure.com/"
AzureOpenAiKey = "3sXbp2pMR6wgu0hCGxQHoxB4uADGpGtYBycbYH30jswvjBaFcvoLJQQJ99AKACYeBjFXJ3w3AAABACOG8T9Y"
AzureOpenAiVersion = "2024-08-01-preview"
AzureDeploymentName='cognidata-gpt-4o'    