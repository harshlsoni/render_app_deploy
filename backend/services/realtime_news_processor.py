"""
Real-time News Processing Service with Intelligent Segmentation
"""
import asyncio
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger
import numpy as np

from ..core.models import AudioSegment, Transcription, TopicSegment, KeyPoint, ModelType
from .huggingface_service import HuggingFaceService
from .database_service import DatabaseService
from .news_stream_service import NewsStreamService
from ..config.settings import settings

@dataclass
class ContentState:
    """Tracks the current state of news content"""
    current_topic: Optional[str] = None
    topic_embedding: Optional[np.ndarray] = None
    topic_start_time: Optional[datetime] = None
    last_keypoints: List[str] = None
    content_hash: Optional[str] = None
    repetition_count: int = 0
    
    def __post_init__(self):
        if self.last_keypoints is None:
            self.last_keypoints = []

class RealtimeNewsProcessor:
    """
    Intelligent real-time news processing system that:
    1. Connects to live news streams
    2. Segments audio intelligently 
    3. Detects topic continuations vs changes
    4. Filters out repetitive content
    5. Processes only meaningful segments
    """
    
    def __init__(self, stream_service=None, db_service=None):
        self.hf_service = HuggingFaceService()
        self.db_service = db_service or DatabaseService()
        self.stream_service = stream_service or NewsStreamService()
        
        # Processing state
        self.content_state = ContentState()
        self.processing_queue = asyncio.Queue()
        self.is_running = False
        
        # Configuration
        self.chunk_duration = 10  # seconds per audio chunk
        self.topic_similarity_threshold = 0.75  # threshold for topic continuation
        self.repetition_threshold = 0.85  # threshold for detecting repetition
        self.max_repetitions = 3  # max allowed repetitions before skipping
        self.silence_threshold = 0.3  # threshold for detecting silence/noise
        
        # Buffers for intelligent segmentation
        self.audio_buffer = []
        self.transcription_buffer = []
        self.last_processed_time = None
    
    async def initialize(self):
        """Initialize all services"""
        logger.info("Initializing real-time news processor...")
        
        await self.db_service.initialize()
        await self.stream_service.initialize()
        
        # Load previous state from database if available
        await self._load_previous_state()
        
        logger.info("Real-time news processor initialized")
    
    async def start_processing(self, news_sources: List[str]):
        """Start real-time news processing"""
        logger.info(f"Starting real-time processing for sources: {news_sources}")
        
        self.is_running = True
        
        # Start the news streams first
        for source in news_sources:
            success = await self.stream_service.start_stream(source)
            if success:
                logger.info(f"Started stream for processing: {source}")
            else:
                logger.warning(f"Failed to start stream for processing: {source}")
        
        # Give streams a moment to initialize
        await asyncio.sleep(2)
        
        # Start concurrent tasks
        tasks = [
            asyncio.create_task(self._audio_capture_loop(news_sources)),
            asyncio.create_task(self._processing_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in processing: {e}")
            await self.stop_processing()
    
    async def stop_processing(self):
        """Stop real-time processing"""
        logger.info("Stopping real-time news processor...")
        self.is_running = False
        await self.stream_service.stop_all_streams()
    
    async def _audio_capture_loop(self, news_sources: List[str]):
        """Continuously capture audio from news sources"""
        while self.is_running:
            try:
                # Get audio chunks from all sources
                for source in news_sources:
                    audio_chunk = await self.stream_service.get_audio_chunk(
                        source, 
                        duration=self.chunk_duration
                    )
                    
                    if audio_chunk:
                        logger.info(f"Got audio chunk from {source}: {audio_chunk.id}")
                        if self._is_meaningful_audio(audio_chunk):
                            # Add to processing queue
                            await self.processing_queue.put({
                                'audio_chunk': audio_chunk,
                                'source': source,
                                'timestamp': datetime.utcnow()
                            })
                            logger.info(f"Added chunk to processing queue. Queue size: {self.processing_queue.qsize()}")
                        else:
                            logger.debug(f"Audio chunk not meaningful: {audio_chunk.id}")
                    else:
                        logger.debug(f"No audio chunk available from {source}")
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in audio capture: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _processing_loop(self):
        """Main processing loop with intelligent segmentation"""
        while self.is_running:
            try:
                # Get next audio chunk to process
                chunk_data = await asyncio.wait_for(
                    self.processing_queue.get(), 
                    timeout=1.0
                )
                
                logger.info(f"Processing audio chunk from queue: {chunk_data['source']}")
                await self._process_audio_chunk(chunk_data)
                
            except asyncio.TimeoutError:
                continue  # No new chunks, continue loop
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
    
    async def _process_audio_chunk(self, chunk_data: Dict):
        """Process a single audio chunk with intelligence"""
        audio_chunk = chunk_data['audio_chunk']
        source = chunk_data['source']
        timestamp = chunk_data['timestamp']
        
        logger.debug(f"Processing chunk from {source} at {timestamp}")
        
        # Step 1: Transcribe audio
        async with self.hf_service:
            transcription = await self.hf_service.transcribe_audio(
                audio_chunk.audio_url,
                ModelType.CUSTOM_FINETUNED
            )
        
        # Step 2: Intelligent content analysis
        should_process = await self._should_process_content(transcription, source)
        
        if not should_process:
            logger.debug("Skipping chunk - repetitive or irrelevant content")
            return
        
        # Step 3: Topic segmentation and analysis
        topic_segments = await self.hf_service.segment_topics(transcription)
        
        # Step 4: Process each segment
        for segment in topic_segments:
            await self._process_topic_segment(segment, source, timestamp)
    
    async def _should_process_content(self, transcription: Transcription, source: str) -> bool:
        """
        Intelligent decision on whether to process this content
        
        Returns False if:
        - Content is repetitive
        - Content is continuation of same topic without new info
        - Content is noise/irrelevant
        """
        
        text = transcription.text.strip()
        
        # Check for empty or very short content
        if len(text) < 20:
            return False
        
        # Generate content hash for repetition detection
        content_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Check for exact repetition
        if content_hash == self.content_state.content_hash:
            self.content_state.repetition_count += 1
            if self.content_state.repetition_count >= self.max_repetitions:
                logger.debug("Skipping - too many repetitions")
                return False
            return False
        
        # Reset repetition count for new content
        self.content_state.repetition_count = 0
        self.content_state.content_hash = content_hash
        
        # Get semantic embedding for topic analysis
        async with self.hf_service:
            sentences = [text]
            embeddings = await self.hf_service._get_sentence_embeddings(sentences)
            current_embedding = embeddings[0] if len(embeddings) > 0 else None
        
        # Check topic continuation vs new topic
        if (self.content_state.topic_embedding is not None and 
            current_embedding is not None):
            
            similarity = self.hf_service._cosine_similarity(
                self.content_state.topic_embedding,
                current_embedding
            )
            
            # If very similar to current topic, check for new information
            if similarity > self.topic_similarity_threshold:
                has_new_info = await self._has_new_information(text)
                if not has_new_info:
                    logger.debug("Skipping - same topic, no new information")
                    return False
            else:
                # New topic detected
                logger.info(f"New topic detected (similarity: {similarity:.3f})")
                await self._handle_topic_change(current_embedding)
        
        # Update current state
        self.content_state.topic_embedding = current_embedding
        
        return True
    
    async def _has_new_information(self, text: str) -> bool:
        """Check if text contains new information compared to recent content"""
        
        # Simple approach: check overlap with recent keypoints
        if not self.content_state.last_keypoints:
            return True
        
        # Generate quick keypoints for comparison
        async with self.hf_service:
            # Create a mock topic segment for keypoint generation
            mock_segment = TopicSegment(
                id="temp_segment",
                transcription_id="temp_transcription", 
                text=text,
                start_index=0,
                end_index=len(text),
                topic_similarity=1.0
            )
            
            new_keypoints = await self.hf_service.generate_keypoints(mock_segment, max_keypoints=3)
            new_keypoint_texts = [kp.text.lower() for kp in new_keypoints]
        
        # Check overlap with recent keypoints
        overlap_count = 0
        for new_kp in new_keypoint_texts:
            for old_kp in self.content_state.last_keypoints:
                # Simple word overlap check
                new_words = set(new_kp.split())
                old_words = set(old_kp.lower().split())
                overlap = len(new_words.intersection(old_words)) / len(new_words.union(old_words))
                
                if overlap > 0.6:  # 60% word overlap threshold
                    overlap_count += 1
                    break
        
        # If most keypoints overlap, probably not new information
        overlap_ratio = overlap_count / len(new_keypoint_texts) if new_keypoint_texts else 0
        return overlap_ratio < 0.7  # Less than 70% overlap means new info
    
    async def _handle_topic_change(self, new_embedding: np.ndarray):
        """Handle transition to a new topic"""
        
        # Save current topic state if it exists
        if self.content_state.current_topic:
            await self._save_topic_completion()
        
        # Initialize new topic state
        self.content_state.current_topic = None  # Will be determined from first keypoint
        self.content_state.topic_embedding = new_embedding
        self.content_state.topic_start_time = datetime.utcnow()
        self.content_state.last_keypoints = []
        
        logger.info("Topic change handled - starting new topic tracking")
    
    async def _process_topic_segment(self, segment: TopicSegment, source: str, timestamp: datetime):
        """Process a topic segment and generate keypoints"""
        
        # Generate keypoints
        async with self.hf_service:
            keypoints = await self.hf_service.generate_keypoints(segment)
        
        if not keypoints:
            return
        
        # Update topic if not set
        if not self.content_state.current_topic and keypoints:
            self.content_state.current_topic = await self._extract_topic_name(keypoints[0].text)
        
        # Store in database
        try:
            await self.db_service.store_topic_segment(segment)
            
            for keypoint in keypoints:
                await self.db_service.store_keypoint(keypoint)
            
            # Update state
            self.content_state.last_keypoints = [kp.text for kp in keypoints[-5:]]  # Keep last 5
            
            logger.info(f"Processed segment with {len(keypoints)} keypoints for topic: {self.content_state.current_topic}")
            
        except Exception as e:
            logger.error(f"Error storing processed content: {e}")
    
    async def _extract_topic_name(self, keypoint_text: str) -> str:
        """Extract topic name from keypoint text"""
        
        # Simple topic extraction - can be enhanced with NER
        text_lower = keypoint_text.lower()
        
        # Common news topics
        topic_keywords = {
            'politics': ['government', 'minister', 'election', 'policy', 'parliament'],
            'sports': ['cricket', 'football', 'match', 'team', 'player', 'score'],
            'weather': ['rain', 'temperature', 'weather', 'storm', 'forecast'],
            'economy': ['market', 'economy', 'business', 'financial', 'trade'],
            'technology': ['technology', 'tech', 'digital', 'software', 'ai'],
            'health': ['health', 'medical', 'hospital', 'doctor', 'treatment']
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return topic
        
        return 'general'
    
    def _is_meaningful_audio(self, audio_chunk: AudioSegment) -> bool:
        """Check if audio chunk contains meaningful content (not just noise)"""
        
        # This is a placeholder - in real implementation, you'd analyze:
        # - Audio amplitude levels
        # - Frequency distribution
        # - Voice activity detection
        # - Background noise levels
        
        # For now, assume all chunks are meaningful
        # You can integrate audio analysis libraries here
        return True
    
    async def _cleanup_loop(self):
        """Periodic cleanup of old data and state management"""
        while self.is_running:
            try:
                # Clean up old processed data (older than 24 hours)
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                await self.db_service.cleanup_old_data(cutoff_time)
                
                # Save current state periodically
                await self._save_current_state()
                
                # Wait 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _save_current_state(self):
        """Save current processing state to database"""
        try:
            state_data = {
                'current_topic': self.content_state.current_topic,
                'topic_start_time': self.content_state.topic_start_time.isoformat() if self.content_state.topic_start_time else None,
                'last_keypoints': self.content_state.last_keypoints,
                'content_hash': self.content_state.content_hash,
                'repetition_count': self.content_state.repetition_count,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            await self.db_service.save_processor_state(state_data)
            
        except Exception as e:
            logger.error(f"Error saving processor state: {e}")
    
    async def _load_previous_state(self):
        """Load previous processing state from database"""
        try:
            state_data = await self.db_service.load_processor_state()
            
            if state_data:
                self.content_state.current_topic = state_data.get('current_topic')
                self.content_state.last_keypoints = state_data.get('last_keypoints', [])
                self.content_state.content_hash = state_data.get('content_hash')
                self.content_state.repetition_count = state_data.get('repetition_count', 0)
                
                if state_data.get('topic_start_time'):
                    self.content_state.topic_start_time = datetime.fromisoformat(state_data['topic_start_time'])
                
                logger.info("Previous processor state loaded")
            
        except Exception as e:
            logger.warning(f"Could not load previous state: {e}")
    
    async def _save_topic_completion(self):
        """Save completed topic information"""
        if self.content_state.current_topic and self.content_state.topic_start_time:
            topic_summary = {
                'topic': self.content_state.current_topic,
                'start_time': self.content_state.topic_start_time.isoformat(),
                'end_time': datetime.utcnow().isoformat(),
                'keypoints_count': len(self.content_state.last_keypoints),
                'last_keypoints': self.content_state.last_keypoints
            }
            
            await self.db_service.save_topic_summary(topic_summary)
            logger.info(f"Topic '{self.content_state.current_topic}' completed and saved")
    
    async def get_current_status(self) -> Dict:
        """Get current processing status"""
        return {
            'is_running': self.is_running,
            'current_topic': self.content_state.current_topic,
            'topic_start_time': self.content_state.topic_start_time.isoformat() if self.content_state.topic_start_time else None,
            'queue_size': self.processing_queue.qsize(),
            'last_keypoints_count': len(self.content_state.last_keypoints),
            'repetition_count': self.content_state.repetition_count
        }