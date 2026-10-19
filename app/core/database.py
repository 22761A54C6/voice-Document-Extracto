from pymongo import MongoClient

from app.core.config import MONGO_URI, MONGO_DB_NAME
from app.core.constants import MONGO_SERVER_SELECTION_TIMEOUT_MS

# Single shared connection, reused across requests and scripts.
# Points at the SAME Atlas cluster + DB as the Image-Text-Pdf service, so both
# services read/write the same "products" and "categories" collections.
# A short server-selection timeout keeps /health from hanging when Mongo is down.
mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS)
db = mongo_client[MONGO_DB_NAME]
