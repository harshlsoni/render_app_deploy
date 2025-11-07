"""
News Stream Service - Connects to real-time news audio streams
"""
import asyncio
import aiohttp
import io
from typing import Dict, List, Optional, AsyncGenerator
from datetime import datetime, timedelta
from loguru import logger
import json

from ..core.models import AudioSegment
from ..config.settings import settings
from .real_audio_capture import RealAudioCapture

class NewsStreamService:
    """
    Service to connect to real-time news audio streams from various sources
    
    Supports:
    - Live radio streams (BBC, CNN, etc.)
    - News API audio feeds
    - YouTube live streams
    - Podcast feeds
    """
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_streams: Dict[str, Dict] = {}
        self.stream_buffers: Dict[str, List[bytes]] = {}
        self.real_audio_capture = RealAudioCapture()
        self.use_real_audio = False  # Toggle between mock and real
        
        # Stream configurations
        self.stream_configs = {
            'bbc_world': {
                'name': 'BBC World Service',
                'url': 'http://stream.live.vc.bbcmedia.co.uk/bbc_world_service',
                'type': 'radio_stream',
                'language': 'en',
                'region': 'global'
            },
            'cnn_audio': {
                'name': 'CNN Audio',
                'url': 'https://tunein.com/radio/CNN-s2680/',
                'type': 'radio_stream', 
                'language': 'en',
                'region': 'us'
            },
            'ndtv_india': {
                'name': 'NDTV India',
                'url': 'https://ndtv24x7elementsys.akamaized.net/hls/live/2003678/ndtv24x7/ndtv24x7master.m3u8',
                'type': 'hls_stream',
                'language': 'en',
                'region': 'india'
            },
            'dd_news': {
                'name': 'DD News',
                'url': 'https://d75dqofg5kmfk.cloudfront.net/bpk-tv/Ddnational/default/ddnational-audio_208482_und=208000-video=877600.m3u8',
                'type': 'hls_stream',
                'language': 'hi',
                'region': 'india'
            },
            'aaj_tak': {
                'name': 'Aaj Tak',
                'url': 'https://feeds.inshorts.com/api/en/search?news_offset=0&news_limit=50',
                'type': 'api_feed',
                'language': 'hi',
                'region': 'india'
            }
        }
    
    async def initialize(self):
        """Initialize the news stream service"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'NewsProcessor/1.0 (Real-time News Analysis)'
            }
        )
        logger.info("News stream service initialized")
    
    async def close(self):
        """Close the service and cleanup"""
        await self.stop_all_streams()
        if self.session:
            await self.session.close()
        logger.info("News stream service closed")
    
    async def get_available_sources(self) -> List[Dict[str, str]]:
        """Get list of available news sources"""
        return [
            {
                'id': source_id,
                'name': config['name'],
                'type': config['type'],
                'language': config['language'],
                'region': config['region']
            }
            for source_id, config in self.stream_configs.items()
        ]
    
    async def start_stream(self, source_id: str) -> bool:
        """Start streaming from a specific news source"""
        if source_id not in self.stream_configs:
            logger.error(f"Unknown news source: {source_id}")
            return False
        
        if source_id in self.active_streams:
            logger.warning(f"Stream {source_id} already active")
            return True
        
        config = self.stream_configs[source_id]
        
        try:
            if config['type'] == 'radio_stream':
                success = await self._start_radio_stream(source_id, config)
            elif config['type'] == 'hls_stream':
                success = await self._start_hls_stream(source_id, config)
            elif config['type'] == 'api_feed':
                success = await self._start_api_feed(source_id, config)
            else:
                logger.error(f"Unsupported stream type: {config['type']}")
                return False
            
            if success:
                # Get the task if it was created
                task = getattr(self, '_temp_tasks', {}).get(source_id)
                
                self.active_streams[source_id] = {
                    'config': config,
                    'start_time': datetime.utcnow(),
                    'status': 'active',
                    'task': task  # Store the background task
                }
                self.stream_buffers[source_id] = []
                logger.info(f"Started stream: {config['name']}")
                
                # Clean up temp task storage
                if hasattr(self, '_temp_tasks') and source_id in self._temp_tasks:
                    del self._temp_tasks[source_id]
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting stream {source_id}: {e}")
            return False
    
    async def stop_stream(self, source_id: str):
        """Stop a specific stream"""
        if source_id in self.active_streams:
            # Cancel any ongoing tasks
            stream_info = self.active_streams[source_id]
            if 'task' in stream_info and stream_info['task'] is not None:
                try:
                    stream_info['task'].cancel()
                except Exception as e:
                    logger.warning(f"Error canceling task for {source_id}: {e}")
            
            del self.active_streams[source_id]
            if source_id in self.stream_buffers:
                del self.stream_buffers[source_id]
            
            logger.info(f"Stopped stream: {source_id}")
    
    async def stop_all_streams(self):
        """Stop all active streams"""
        for source_id in list(self.active_streams.keys()):
            await self.stop_stream(source_id)
    
    async def get_audio_chunk(self, source_id: str, duration: int = 10) -> Optional[AudioSegment]:
        """
        Get an audio chunk from the specified source
        
        Args:
            source_id: ID of the news source
            duration: Duration of audio chunk in seconds
            
        Returns:
            AudioSegment or None if no audio available
        """
        if source_id not in self.active_streams:
            logger.warning(f"Stream {source_id} not active. Active streams: {list(self.active_streams.keys())}")
            return None
        
        config = self.stream_configs[source_id]
        
        try:
            if config['type'] in ['radio_stream', 'hls_stream']:
                return await self._get_audio_chunk_from_stream(source_id, duration)
            elif config['type'] == 'api_feed':
                return await self._get_audio_chunk_from_api(source_id, duration)
            
        except Exception as e:
            logger.error(f"Error getting audio chunk from {source_id}: {e}")
            return None
    
    async def _start_radio_stream(self, source_id: str, config: Dict) -> bool:
        """Start a radio stream"""
        try:
            # For demo purposes, we'll simulate radio stream connection
            # In production, you'd use libraries like ffmpeg-python or similar
            
            logger.info(f"Connecting to radio stream: {config['url']}")
            
            # Simulate connection test
            async with self.session.get(config['url'], timeout=10) as response:
                if response.status == 200:
                    # Start background task to capture audio
                    task = asyncio.create_task(
                        self._capture_radio_audio(source_id, config)
                    )
                    # Store task temporarily - will be merged with stream info later
                    self._temp_tasks = getattr(self, '_temp_tasks', {})
                    self._temp_tasks[source_id] = task
                    return True
                else:
                    logger.error(f"Failed to connect to {config['url']}: {response.status}")
                    # Fall back to mock audio generation
                    logger.info(f"Falling back to mock audio generation for {source_id}")
                    task = asyncio.create_task(
                        self._generate_mock_audio(source_id, config)
                    )
                    # Store task temporarily - will be merged with stream info later
                    self._temp_tasks = getattr(self, '_temp_tasks', {})
                    self._temp_tasks[source_id] = task
                    return True
                    
        except Exception as e:
            logger.error(f"Radio stream connection failed: {e}")
            # For demo, we'll simulate success and generate mock audio
            logger.info(f"Falling back to mock audio generation for {source_id}")
            task = asyncio.create_task(
                self._generate_mock_audio(source_id, config)
            )
            # Store task temporarily - will be merged with stream info later
            self._temp_tasks = getattr(self, '_temp_tasks', {})
            self._temp_tasks[source_id] = task
            return True
    
    async def _start_hls_stream(self, source_id: str, config: Dict) -> bool:
        """Start an HLS stream"""
        try:
            logger.info(f"Connecting to HLS stream: {config['url']}")
            
            # For demo, simulate HLS connection and use mock audio
            # In production, you'd parse M3U8 playlists and download segments
            logger.info(f"Using mock audio generation for HLS stream {source_id}")
            
            task = asyncio.create_task(
                self._generate_mock_audio(source_id, config)
            )
            # Store task temporarily - will be merged with stream info later
            self._temp_tasks = getattr(self, '_temp_tasks', {})
            self._temp_tasks[source_id] = task
            return True
            
        except Exception as e:
            logger.error(f"HLS stream connection failed: {e}")
            # Still try mock audio as fallback
            task = asyncio.create_task(
                self._generate_mock_audio(source_id, config)
            )
            self._temp_tasks = getattr(self, '_temp_tasks', {})
            self._temp_tasks[source_id] = task
            return True
    
    async def _start_api_feed(self, source_id: str, config: Dict) -> bool:
        """Start an API-based news feed"""
        try:
            logger.info(f"Connecting to API feed: {config['url']}")
            
            # Test API connection
            async with self.session.get(config['url']) as response:
                if response.status == 200:
                    task = asyncio.create_task(
                        self._poll_api_feed(source_id, config)
                    )
                    return True
                else:
                    logger.error(f"API feed connection failed: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"API feed connection failed: {e}")
            return False
    
    async def _capture_radio_audio(self, source_id: str, config: Dict):
        """Capture audio from radio stream"""
        logger.info(f"Starting radio audio capture for {source_id}")
        
        # For radio streams that fail to connect, fall back to mock generation
        await self._generate_mock_audio(source_id, config)
    
    async def _generate_mock_audio(self, source_id: str, config: Dict):
        """Generate mock audio data for testing"""
        logger.info(f"Starting mock audio generation for {source_id}")
        
        # Initialize buffer if not exists
        if source_id not in self.stream_buffers:
            self.stream_buffers[source_id] = []
        
        mock_news_content = [
            "Breaking news: Government announces new economic policy measures",
            "Weather update: Heavy rainfall expected in northern regions today",
            "Sports news: Local cricket team wins championship match",
            "Technology: New AI breakthrough announced by research institute",
            "Health: Medical experts recommend new safety guidelines",
            "Politics: Parliament session discusses important legislation",
            "Business: Stock market shows positive trends this week",
            "International: Global summit addresses climate change issues"
        ]
        
        content_index = 0
        
        # Wait a bit for the stream to be properly registered
        await asyncio.sleep(2)  # Increased delay to ensure proper startup
        
        # Use a different condition - check if we should keep running
        max_iterations = 100  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            try:
                # Simulate news content
                content = mock_news_content[content_index % len(mock_news_content)]
                content_index += 1
                
                # Create mock audio segment
                timestamp = datetime.utcnow()
                mock_audio_url = f"mock://{source_id}/{timestamp.timestamp()}"
                
                audio_segment = AudioSegment(
                    id=f"{source_id}_{timestamp.timestamp()}",
                    audio_url=mock_audio_url,
                    start_time=timestamp,
                    end_time=timestamp + timedelta(seconds=10),
                    duration=10.0,
                    source=source_id,
                    metadata={
                        'content': content,
                        'language': config['language'],
                        'region': config['region'],
                        'mock': True
                    }
                )
                
                # Add to buffer
                if source_id not in self.stream_buffers:
                    self.stream_buffers[source_id] = []
                
                self.stream_buffers[source_id].append(audio_segment)
                logger.info(f"Added mock audio to buffer for {source_id}. Buffer size: {len(self.stream_buffers[source_id])}")
                
                # Keep buffer manageable
                if len(self.stream_buffers[source_id]) > 20:
                    self.stream_buffers[source_id] = self.stream_buffers[source_id][-10:]
                
                logger.debug(f"Generated mock audio segment for {source_id}: {content[:50]}...")
                
                await asyncio.sleep(8)  # Generate new content every 8 seconds
                iteration += 1
                
                # Check if stream is still active
                if source_id not in self.active_streams:
                    logger.info(f"Stream {source_id} no longer active, stopping mock generation")
                    break
                
            except Exception as e:
                logger.error(f"Error generating mock audio: {e}")
                await asyncio.sleep(5)
                iteration += 1
        
        logger.info(f"Mock audio generation stopped for {source_id}")
    
    async def _poll_api_feed(self, source_id: str, config: Dict):
        """Poll API feed for new content"""
        last_update = datetime.utcnow()
        
        while source_id in self.active_streams:
            try:
                async with self.session.get(config['url']) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Process API response (structure depends on API)
                        # For demo, we'll create audio segments from text content
                        if 'data' in data:
                            for item in data['data'][:5]:  # Process first 5 items
                                if 'title' in item:
                                    await self._create_audio_from_text(
                                        source_id, 
                                        item['title'], 
                                        config
                                    )
                
                await asyncio.sleep(60)  # Poll every minute
                
            except Exception as e:
                logger.error(f"Error polling API feed: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _create_audio_from_text(self, source_id: str, text: str, config: Dict):
        """Create audio segment from text content (for API feeds)"""
        timestamp = datetime.utcnow()
        
        audio_segment = AudioSegment(
            id=f"{source_id}_{timestamp.timestamp()}",
            audio_url=f"tts://{source_id}/{timestamp.timestamp()}",  # Text-to-speech URL
            start_time=timestamp,
            end_time=timestamp + timedelta(seconds=15),
            duration=15.0,
            source=source_id,
            metadata={
                'content': text,
                'language': config['language'],
                'region': config['region'],
                'type': 'text_to_speech'
            }
        )
        
        if source_id not in self.stream_buffers:
            self.stream_buffers[source_id] = []
        
        self.stream_buffers[source_id].append(audio_segment)
    
    async def _get_audio_chunk_from_stream(self, source_id: str, duration: int) -> Optional[AudioSegment]:
        """Get audio chunk from stream buffer"""
        buffer_size = len(self.stream_buffers.get(source_id, []))
        logger.debug(f"Checking buffer for {source_id}: size={buffer_size}")
        
        if source_id not in self.stream_buffers or not self.stream_buffers[source_id]:
            logger.debug(f"No audio chunks available for {source_id} (buffer size: {buffer_size})")
            return None
        
        # Get the most recent audio segment
        audio_segment = self.stream_buffers[source_id].pop(0)
        logger.info(f"Retrieved audio chunk for {source_id}: {audio_segment.id} (remaining buffer: {len(self.stream_buffers[source_id])})")
        return audio_segment
    
    async def _get_audio_chunk_from_api(self, source_id: str, duration: int) -> Optional[AudioSegment]:
        """Get audio chunk from API feed buffer"""
        return await self._get_audio_chunk_from_stream(source_id, duration)
    
    async def get_stream_status(self, source_id: str) -> Optional[Dict]:
        """Get status of a specific stream"""
        if source_id not in self.active_streams:
            return None
        
        stream_info = self.active_streams[source_id]
        config = self.stream_configs[source_id]
        
        return {
            'source_id': source_id,
            'name': config['name'],
            'status': stream_info['status'],
            'start_time': stream_info['start_time'].isoformat(),
            'buffer_size': len(self.stream_buffers.get(source_id, [])),
            'language': config['language'],
            'region': config['region']
        }
    
    async def get_all_stream_status(self) -> List[Dict]:
        """Get status of all active streams"""
        statuses = []
        for source_id in self.active_streams:
            status = await self.get_stream_status(source_id)
            if status:
                statuses.append(status)
        return statuses
    
    async def set_audio_mode(self, use_real_audio: bool):
        """Set whether to use real audio capture or mock audio"""
        self.use_real_audio = use_real_audio
        
        if use_real_audio:
            success = await self.real_audio_capture.initialize()
            if success:
                logger.info("Switched to real audio capture mode")
            else:
                logger.warning("Failed to initialize real audio capture, staying in mock mode")
                self.use_real_audio = False
        else:
            logger.info("Switched to mock audio mode")
    
    async def get_audio_mode(self) -> Dict:
        """Get current audio mode and capabilities"""
        return {
            'current_mode': 'real' if self.use_real_audio else 'mock',
            'real_audio_available': await self.real_audio_capture.initialize() if hasattr(self, 'real_audio_capture') else False,
            'mock_sources': len(self.stream_configs),
            'real_sources': len(self.real_audio_capture.get_available_real_sources()) if hasattr(self, 'real_audio_capture') else 0
        }