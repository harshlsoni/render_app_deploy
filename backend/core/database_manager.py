"""
Database Manager - Unified database interface with fallback mechanisms
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from loguru import logger

# Optional imports with fallbacks
try:
    import aiosqlite
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    logger.warning("aiosqlite not available - SQLite fallback disabled")

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("motor/pymongo not available - MongoDB disabled")

try:
    from ..config.settings import settings
except ImportError:
    # Fallback settings
    class FallbackSettings:
        MONGODB_URL = "mongodb://localhost:27017"
        MONGODB_DATABASE = "news_processing"
    settings = FallbackSettings()

class DatabaseManager:
    """Unified database manager with MongoDB primary and SQLite fallback"""
    
    def __init__(self):
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.mongo_db = None
        self.sqlite_path = "fallback.db"
        self.current_backend = None
        self.connection_retries = 3
        self.retry_delay = 2.0
        
    async def initialize(self) -> bool:
        """Initialize database with fallback mechanism"""
        # Try MongoDB first
        if await self._init_mongodb():
            self.current_backend = "mongodb"
            logger.info("Database Manager initialized with MongoDB")
            return True
            
        # Fallback to SQLite
        if await self._init_sqlite():
            self.current_backend = "sqlite"
            logger.warning("Database Manager initialized with SQLite fallback")
            return True
            
        # Emergency in-memory fallback
        self.current_backend = "memory"
        self._memory_store = {}
        logger.error("Database Manager using in-memory fallback")
        return True
    
    async def _init_mongodb(self) -> bool:
        """Initialize MongoDB connection with retry logic"""
        if not MONGODB_AVAILABLE:
            logger.warning("MongoDB libraries not available")
            return False
            
        for attempt in range(self.connection_retries):
            try:
                self.mongo_client = AsyncIOMotorClient(
                    settings.MONGODB_URL,
                    serverSelectionTimeoutMS=5000
                )
                self.mongo_db = self.mongo_client[settings.MONGODB_DATABASE]
                
                # Test connection
                await self.mongo_client.admin.command('ping')
                await self._create_mongo_indexes()
                return True
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.warning(f"MongoDB connection attempt {attempt + 1} failed: {e}")
                if attempt < self.connection_retries - 1:
                    await asyncio.sleep(self.retry_delay)
            except Exception as e:
                logger.warning(f"MongoDB connection error: {e}")
                break
                    
        return False
    
    async def _init_sqlite(self) -> bool:
        """Initialize SQLite fallback database"""
        if not SQLITE_AVAILABLE:
            logger.warning("SQLite libraries not available")
            return False
            
        try:
            async with aiosqlite.connect(self.sqlite_path) as db:
                await self._create_sqlite_tables(db)
                await db.commit()
            return True
        except Exception as e:
            logger.error(f"SQLite initialization failed: {e}")
            return False
    
    async def _create_mongo_indexes(self):
        """Create MongoDB indexes"""
        try:
            collections = {
                "keypoints": ["created_at", "segment_id", "importance_score"],
                "transcriptions": ["segment_id", "created_at"],
                "audio_segments": ["created_at", "source", "processing_status"]
            }
            
            for collection, indexes in collections.items():
                for index in indexes:
                    await self.mongo_db[collection].create_index(index)
                    
        except Exception as e:
            logger.warning(f"Error creating MongoDB indexes: {e}")
    
    async def _create_sqlite_tables(self, db):
        """Create SQLite tables"""
        tables = [
            """CREATE TABLE IF NOT EXISTS keypoints (
                id TEXT PRIMARY KEY,
                segment_id TEXT,
                keypoint_text TEXT,
                importance_score REAL,
                model_used TEXT,
                created_at TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS transcriptions (
                id TEXT PRIMARY KEY,
                segment_id TEXT,
                transcript TEXT,
                confidence REAL,
                model_used TEXT,
                created_at TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS audio_segments (
                id TEXT PRIMARY KEY,
                audio_url TEXT,
                source TEXT,
                processing_status TEXT,
                created_at TIMESTAMP
            )"""
        ]
        
        for table_sql in tables:
            await db.execute(table_sql)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health"""
        if self.current_backend == "mongodb":
            try:
                await self.mongo_client.admin.command('ping')
                return {"status": "healthy", "backend": "mongodb", "connected": True}
            except Exception as e:
                return {"status": "unhealthy", "backend": "mongodb", "error": str(e)}
                
        elif self.current_backend == "sqlite":
            if not SQLITE_AVAILABLE:
                return {"status": "unhealthy", "backend": "sqlite", "error": "SQLite libraries not available"}
            try:
                async with aiosqlite.connect(self.sqlite_path) as db:
                    await db.execute("SELECT 1")
                return {"status": "healthy", "backend": "sqlite", "connected": True}
            except Exception as e:
                return {"status": "unhealthy", "backend": "sqlite", "error": str(e)}
                
        else:
            return {"status": "degraded", "backend": "memory", "connected": True}
    
    async def store_keypoint(self, keypoint_data: Dict[str, Any]) -> bool:
        """Store keypoint with backend-specific implementation"""
        try:
            if self.current_backend == "mongodb":
                await self.mongo_db.keypoints.insert_one(keypoint_data)
                
            elif self.current_backend == "sqlite" and SQLITE_AVAILABLE:
                async with aiosqlite.connect(self.sqlite_path) as db:
                    await db.execute(
                        """INSERT OR REPLACE INTO keypoints 
                           (id, segment_id, keypoint_text, importance_score, model_used, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (keypoint_data["_id"], keypoint_data["segment_id"], 
                         keypoint_data["keypoint_text"], keypoint_data["importance_score"],
                         keypoint_data["model_used"], keypoint_data["created_at"])
                    )
                    await db.commit()
                    
            else:  # memory fallback
                if "keypoints" not in self._memory_store:
                    self._memory_store["keypoints"] = []
                self._memory_store["keypoints"].append(keypoint_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error storing keypoint: {e}")
            return False
    
    async def get_recent_keypoints(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent keypoints from current backend"""
        try:
            if self.current_backend == "mongodb":
                cursor = self.mongo_db.keypoints.find().sort("created_at", -1).limit(limit)
                return await cursor.to_list(length=limit)
                
            elif self.current_backend == "sqlite" and SQLITE_AVAILABLE:
                async with aiosqlite.connect(self.sqlite_path) as db:
                    cursor = await db.execute(
                        "SELECT * FROM keypoints ORDER BY created_at DESC LIMIT ?",
                        (limit,)
                    )
                    rows = await cursor.fetchall()
                    return [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
                    
            else:  # memory fallback
                keypoints = self._memory_store.get("keypoints", [])
                return sorted(keypoints, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]
                
        except Exception as e:
            logger.error(f"Error getting recent keypoints: {e}")
            return []

    async def get_keypoint_by_id(self, keypoint_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific keypoint by ID"""
        try:
            if self.current_backend == "mongodb":
                return await self.mongo_db.keypoints.find_one({"_id": keypoint_id})
                
            elif self.current_backend == "sqlite" and SQLITE_AVAILABLE:
                async with aiosqlite.connect(self.sqlite_path) as db:
                    cursor = await db.execute(
                        "SELECT * FROM keypoints WHERE id = ?",
                        (keypoint_id,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        return dict(zip([col[0] for col in cursor.description], row))
                    return None
                    
            else:  # memory fallback
                keypoints = self._memory_store.get("keypoints", [])
                for kp in keypoints:
                    if kp.get("_id") == keypoint_id or kp.get("id") == keypoint_id:
                        return kp
                return None
                
        except Exception as e:
            logger.error(f"Error getting keypoint by ID {keypoint_id}: {e}")
            return None
    
    async def close(self):
        """Close database connections"""
        if self.mongo_client:
            self.mongo_client.close()
        logger.info(f"Database Manager ({self.current_backend}) closed")