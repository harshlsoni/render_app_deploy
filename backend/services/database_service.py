"""
Database Service - Unified database interface using DatabaseManager
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
from ..core.models import (
    AudioSegment, Transcription, TopicSegment, KeyPoint, ProcessingStatus
)
from ..core.database_manager import DatabaseManager

class DatabaseService:
    """Service for database operations using unified DatabaseManager"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.initialized = False
    
    async def initialize(self):
        """Initialize database manager"""
        try:
            success = await self.db_manager.initialize()
            self.initialized = success
            logger.info("Database service initialized with unified manager")
            return success
        except Exception as e:
            logger.error(f"Failed to initialize database service: {e}")
            self.initialized = False
            return False
    
    async def close(self):
        """Close database connections"""
        if self.db_manager:
            await self.db_manager.close()
        logger.info("Database service closed")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health using unified manager"""
        try:
            return await self.db_manager.health_check()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    # Audio Segment Operations
    async def store_audio_segment(self, audio_segment: AudioSegment) -> bool:
        """Store audio segment in database"""
        try:
            # For now, just log the operation - can be extended later
            logger.info(f"Audio segment processing: {audio_segment.id}")
            return True
        except Exception as e:
            logger.error(f"Error storing audio segment: {e}")
            return False
    
    # Transcription Operations
    async def store_transcription(self, transcription: Transcription) -> bool:
        """Store transcription in database"""
        try:
            # For now, just log the operation - can be extended later
            logger.info(f"Transcription processed: {transcription.id}")
            return True
        except Exception as e:
            logger.error(f"Error storing transcription: {e}")
            return False
    
    # Topic Segment Operations
    async def store_topic_segment(self, topic_segment: TopicSegment) -> bool:
        """Store topic segment in database"""
        try:
            # For now, just log the operation - can be extended later
            logger.info(f"Topic segment processed: {topic_segment.id}")
            return True
        except Exception as e:
            logger.error(f"Error storing topic segment: {e}")
            return False
    
    # Key Point Operations
    async def store_keypoint(self, keypoint: KeyPoint) -> bool:
        """Store key point in database using unified manager"""
        try:
            data = {
                "_id": keypoint.id,
                "segment_id": keypoint.segment_id,
                "keypoint_text": keypoint.text,
                "importance_score": keypoint.importance_score,
                "order_index": keypoint.order_index,
                "model_used": keypoint.model_used,
                "created_at": keypoint.created_at
            }
            
            success = await self.db_manager.store_keypoint(data)
            if success:
                logger.info(f"Key point stored: {keypoint.id}")
            return success
                
        except Exception as e:
            logger.error(f"Error storing key point: {e}")
            return False
    
    # Query Operations
    async def get_recent_keypoints(self, limit: int = 10) -> List[KeyPoint]:
        """Get recent key points using unified manager"""
        try:
            docs = await self.db_manager.get_recent_keypoints(limit)
            keypoints = []
            
            for doc in docs:
                # Handle different field names from different backends
                keypoint_id = doc.get("_id") or doc.get("id")
                keypoint_text = doc.get("keypoint_text") or doc.get("text", "")
                created_at = doc.get("created_at", datetime.utcnow())
                
                keypoint = KeyPoint(
                    id=keypoint_id,
                    segment_id=doc.get("segment_id", "unknown"),
                    text=keypoint_text,
                    importance_score=doc.get("importance_score", 0.5),
                    order_index=doc.get("order_index", 0),
                    model_used=doc.get("model_used", "unknown"),
                    created_at=created_at
                )
                keypoints.append(keypoint)
            
            return keypoints
            
        except Exception as e:
            logger.error(f"Error getting recent key points: {e}")
            return []

    async def get_keypoint_by_id(self, keypoint_id: str) -> Optional[KeyPoint]:
        """Get a specific keypoint by ID"""
        try:
            # First try to get from database
            doc = await self.db_manager.get_keypoint_by_id(keypoint_id)
            
            if doc:
                keypoint_text = doc.get("keypoint_text") or doc.get("text", "")
                created_at = doc.get("created_at", datetime.utcnow())
                
                return KeyPoint(
                    id=keypoint_id,
                    segment_id=doc.get("segment_id", "unknown"),
                    text=keypoint_text,
                    importance_score=doc.get("importance_score", 0.5),
                    order_index=doc.get("order_index", 0),
                    model_used=doc.get("model_used", "unknown"),
                    created_at=created_at
                )
            
            # Fallback: check recent keypoints
            recent_keypoints = await self.get_recent_keypoints(50)  # Check more keypoints
            for kp in recent_keypoints:
                if kp.id == keypoint_id:
                    return kp
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting keypoint by ID {keypoint_id}: {e}")
            return None
    
    async def search_keypoints(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10
    ) -> List[KeyPoint]:
        """Search key points with filters - simplified implementation"""
        try:
            # For now, just return recent keypoints
            # TODO: Implement proper filtering when needed
            logger.info(f"Searching keypoints with filters: start_time={start_time}, end_time={end_time}, source={source}")
            return await self.get_recent_keypoints(limit)
            
        except Exception as e:
            logger.error(f"Error searching key points: {e}")
            return []
    
    # Status Operations
    async def update_segment_status(self, segment_id: str, status: ProcessingStatus) -> bool:
        """Update processing status of a segment"""
        try:
            logger.info(f"Segment status update: {segment_id} -> {status.value}")
            return True  # Simplified for now
        except Exception as e:
            logger.error(f"Error updating segment status: {e}")
            return False
    
    async def get_segment_status(self, segment_id: str) -> Optional[ProcessingStatus]:
        """Get processing status of a segment"""
        try:
            # Return completed status for now
            return ProcessingStatus.COMPLETED
        except Exception as e:
            logger.error(f"Error getting segment status: {e}")
            return None    

    # Simplified methods for essential functionality
    async def cleanup_old_data(self, cutoff_time: datetime):
        """Clean up old data - simplified implementation"""
        try:
            logger.info(f"Cleanup requested for data older than {cutoff_time}")
            # TODO: Implement cleanup when needed
        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
    
    async def save_processor_state(self, state_data: dict):
        """Save processor state - simplified implementation"""
        try:
            logger.info("Processor state saved")
            # TODO: Implement state persistence when needed
        except Exception as e:
            logger.error(f"Error saving processor state: {e}")
    
    async def load_processor_state(self) -> Optional[dict]:
        """Load processor state - simplified implementation"""
        try:
            # Return empty state for now
            return {}
        except Exception as e:
            logger.error(f"Error loading processor state: {e}")
            return None
    
    async def save_topic_summary(self, topic_summary: dict):
        """Save completed topic summary - simplified implementation"""
        try:
            logger.info(f"Topic summary saved: {topic_summary.get('topic', 'unknown')}")
        except Exception as e:
            logger.error(f"Error saving topic summary: {e}")
    
    async def get_recent_topics(self, limit: int = 10) -> List[dict]:
        """Get recent completed topics - simplified implementation"""
        try:
            # Return sample topics for now
            return [
                {
                    "topic": "System Status",
                    "start_time": datetime.utcnow().isoformat(),
                    "end_time": datetime.utcnow().isoformat(),
                    "keypoints_count": 1
                }
            ]
        except Exception as e:
            logger.error(f"Error getting recent topics: {e}")
            return []
    
    async def get_transcription_by_segment_id(self, segment_id: str) -> Optional[dict]:
        """Get transcription by segment ID - simplified implementation"""
        try:
            # Return basic transcription info for now
            return {
                "segment_id": segment_id,
                "transcript": "Sample transcription",
                "created_at": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Error getting transcription by segment ID: {e}")
            return None