import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME

# Use certifi CA bundle only for MongoDB Atlas (SRV/TLS connections)
if MONGO_URL and ("mongodb+srv" in MONGO_URL or "mongodb.net" in MONGO_URL):
    client = AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where())
else:
    client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
