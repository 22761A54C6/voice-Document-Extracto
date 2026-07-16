from pymongo import MongoClient

from app.config import MONGO_URI, MONGO_DB_NAME

# Single shared connection, reused across requests and scripts.
# Points at the SAME Atlas cluster + DB as AI-service-Ai, so both
# services read/write the same "products" and "categories" collections.
mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB_NAME]
