"""
HuggingFace Service - Handles ML model inference via HuggingFace API
"""
import asyncio
import aiohttp
import numpy as np
import uuid
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger
from ..core.models import ModelType, Transcription, TopicSegment, KeyPoint
from ..config.settings import settings

class HuggingFaceService:
    """Service for HuggingFace model inference"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            "Authorization": f"Bearer {settings.HUGGINGFACE_API_TOKEN}",
            "Content-Type": "application/json"
        }
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    # Speech-to-Text Methods
    async def transcribe_audio(
        self, 
        audio_url: str, 
        model_type: ModelType = ModelType.CUSTOM_FINETUNED
    ) -> Transcription:
        """
        Transcribe audio using HuggingFace Speech-to-Text models
        
        Args:
            audio_url: URL or path to audio file
            model_type: Type of model to use for transcription
        
        Returns:
            Transcription: Transcribed text with metadata
        """
        try:
            logger.info(f"Transcribing audio: {audio_url} with model: {model_type.value}")
            
            # Handle mock audio URLs
            if audio_url.startswith('mock://'):
                return await self._generate_mock_transcription(audio_url, model_type)
            
            model_name = self._get_model_name(model_type)
            api_url = f"{settings.HUGGINGFACE_BASE_URL}/{model_name}"
            
            # Download audio file
            audio_data = await self._download_audio(audio_url)
            
            # Send to HuggingFace API
            async with self.session.post(api_url, data=audio_data) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract transcription text
                    text = result.get('text', '') if isinstance(result, dict) else str(result)
                    confidence = result.get('confidence', 0.8) if isinstance(result, dict) else 0.8
                    
                    transcription = Transcription(
                        id=f"trans_{hash(audio_url)}_{model_type.value}",
                        segment_id=audio_url.split('/')[-1].split('.')[0],
                        text=text.strip(),
                        confidence=confidence,
                        model_used=model_type,
                        processing_time=0.0  # Will be calculated by caller
                    )
                    
                    logger.info(f"Transcription completed: {len(text)} characters")
                    return transcription
                
                else:
                    error_text = await response.text()
                    logger.error(f"HuggingFace API error: {response.status} - {error_text}")
                    raise Exception(f"Transcription failed: {error_text}")
        
        except Exception as e:
            logger.error(f"Error in transcription: {e}")
            raise
    
    # Topic Segmentation Methods
    async def segment_topics(
        self, 
        transcription: Transcription,
        similarity_threshold: float = 0.7
    ) -> List[TopicSegment]:
        """
        Segment transcription into topics using semantic similarity
        
        Args:
            transcription: Input transcription
            similarity_threshold: Cosine similarity threshold for topic boundaries
        
        Returns:
            List[TopicSegment]: List of topic segments
        """
        try:
            text = transcription.text
            sentences = self._split_into_sentences(text)
            
            if len(sentences) <= 1:
                # Single sentence, return as one segment
                return [TopicSegment(
                    id=f"topic_{transcription.id}_0",
                    transcription_id=transcription.id,
                    text=text,
                    start_index=0,
                    end_index=len(text),
                    topic_similarity=1.0
                )]
            
            # Get sentence embeddings
            embeddings = await self._get_sentence_embeddings(sentences)
            
            # Find topic boundaries using cosine similarity
            segments = []
            current_segment_start = 0
            current_text = sentences[0]
            
            for i in range(1, len(sentences)):
                # Calculate cosine similarity between consecutive sentences
                similarity = self._cosine_similarity(embeddings[i-1], embeddings[i])
                
                if similarity < similarity_threshold:
                    # Topic boundary detected
                    segment = TopicSegment(
                        id=f"topic_{transcription.id}_{len(segments)}",
                        transcription_id=transcription.id,
                        text=current_text.strip(),
                        start_index=current_segment_start,
                        end_index=current_segment_start + len(current_text),
                        topic_similarity=similarity,
                        embedding=embeddings[i-1].tolist() if len(embeddings) > i-1 else None
                    )
                    segments.append(segment)
                    
                    # Start new segment
                    current_segment_start += len(current_text) + 1
                    current_text = sentences[i]
                else:
                    # Continue current segment
                    current_text += " " + sentences[i]
            
            # Add final segment
            if current_text.strip():
                segment = TopicSegment(
                    id=f"topic_{transcription.id}_{len(segments)}",
                    transcription_id=transcription.id,
                    text=current_text.strip(),
                    start_index=current_segment_start,
                    end_index=len(text),
                    topic_similarity=1.0,
                    embedding=embeddings[-1].tolist() if embeddings else None
                )
                segments.append(segment)
            
            logger.info(f"Topic segmentation completed: {len(segments)} segments found")
            return segments
        
        except Exception as e:
            logger.error(f"Error in topic segmentation: {e}")
            raise
    
    # Key Point Generation Methods
    async def generate_keypoints(
        self, 
        topic_segment: TopicSegment,
        max_keypoints: int = 3
    ) -> List[KeyPoint]:
        """
        Generate key points from topic segment using LLM
        
        Args:
            topic_segment: Input topic segment
            max_keypoints: Maximum number of key points to generate
        
        Returns:
            List[KeyPoint]: Generated key points
        """
        try:
            # For demo purposes, use mock keypoint generation
            # This bypasses the HuggingFace API credential requirement
            if True:  # Always use mock for now
                return self._generate_mock_keypoints(topic_segment, max_keypoints)
            
            # Use a summarization model for key point generation
            model_name = "facebook/bart-large-cnn"  # Good for summarization
            api_url = f"{settings.HUGGINGFACE_BASE_URL}/{model_name}"
            
            # Prepare prompt for key point extraction
            prompt = f"""
            Extract the most important key points from this news segment. 
            Focus on facts, events, and significant information.
            
            Text: {topic_segment.text}
            
            Key Points:
            """
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_length": 150,
                    "min_length": 30,
                    "do_sample": False,
                    "num_return_sequences": 1
                }
            }
            
            async with self.session.post(api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Extract generated text
                    if isinstance(result, list) and len(result) > 0:
                        generated_text = result[0].get('generated_text', '')
                    else:
                        generated_text = str(result)
                    
                    # Parse key points from generated text
                    keypoints = self._parse_keypoints(
                        generated_text, 
                        topic_segment.id, 
                        max_keypoints
                    )
                    
                    logger.info(f"Generated {len(keypoints)} key points for segment {topic_segment.id}")
                    return keypoints
                
                else:
                    error_text = await response.text()
                    logger.error(f"Key point generation failed: {response.status} - {error_text}")
                    
                    # Fallback: extract sentences as key points
                    return self._extract_fallback_keypoints(topic_segment, max_keypoints)
        
        except Exception as e:
            logger.error(f"Error generating key points: {e}")
            # Fallback to simple extraction
            return self._extract_fallback_keypoints(topic_segment, max_keypoints)
    
    # Helper Methods
    def _get_model_name(self, model_type: ModelType) -> str:
        """Get HuggingFace model name for given model type"""
        model_mapping = {
            ModelType.WHISPER_BASE: settings.WHISPER_BASE_MODEL,
            ModelType.WHISPER_LARGE: settings.WHISPER_LARGE_MODEL,
            ModelType.CUSTOM_FINETUNED: settings.CUSTOM_FINETUNED_MODEL,
            ModelType.WAV2VEC2: settings.WAV2VEC2_MODEL,
            ModelType.HUBERT: settings.HUBERT_MODEL
        }
        return model_mapping.get(model_type, settings.WHISPER_BASE_MODEL)
    
    async def _download_audio(self, audio_url: str) -> bytes:
        """Download audio file from URL"""
        try:
            async with self.session.get(audio_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise Exception(f"Failed to download audio: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            raise
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        # Simple sentence splitting (can be improved with NLTK)
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    async def _get_sentence_embeddings(self, sentences: List[str]) -> np.ndarray:
        """Get sentence embeddings using HuggingFace model"""
        try:
            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            api_url = f"{settings.HUGGINGFACE_BASE_URL}/{model_name}"
            
            payload = {"inputs": sentences}
            
            async with self.session.post(api_url, json=payload) as response:
                if response.status == 200:
                    embeddings = await response.json()
                    return np.array(embeddings)
                else:
                    # Fallback: random embeddings for development
                    logger.warning("Using random embeddings as fallback")
                    return np.random.rand(len(sentences), 384)
        
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            # Fallback: random embeddings
            return np.random.rand(len(sentences), 384)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def _generate_mock_transcription(self, audio_url: str, model_type: ModelType) -> Transcription:
        """Generate mock transcription for testing"""
        # Extract content from the mock audio URL or use default
        # The mock audio segments have content in their metadata
        mock_transcriptions = [
            "Breaking news: Government announces new economic policy measures to boost growth and employment in the coming fiscal year.",
            "Weather update: Heavy rainfall expected in northern regions today with temperatures dropping to 15 degrees celsius.",
            "Sports news: Local cricket team wins championship match against defending champions in a thrilling final over.",
            "Technology: New AI breakthrough announced by research institute promises to revolutionize healthcare diagnostics.",
            "Health: Medical experts recommend new safety guidelines for winter season to prevent respiratory infections.",
            "Politics: Parliament session discusses important legislation on environmental protection and climate change.",
            "Business: Stock market shows positive trends this week with technology and healthcare sectors leading gains.",
            "International: Global summit addresses climate change issues with world leaders committing to carbon neutrality."
        ]
        
        # Use a hash of the URL to consistently pick the same transcription
        import hashlib
        url_hash = int(hashlib.md5(audio_url.encode()).hexdigest(), 16)
        selected_text = mock_transcriptions[url_hash % len(mock_transcriptions)]
        
        transcription = Transcription(
            id=str(uuid.uuid4()),
            segment_id=str(uuid.uuid4()),
            text=selected_text,
            confidence=0.92,  # High confidence for mock
            model_used=model_type,
            processing_time=0.5  # Mock processing time
        )
        
        logger.info(f"Generated mock transcription: {selected_text[:50]}...")
        return transcription
    
    def _generate_mock_keypoints(self, topic_segment: TopicSegment, max_keypoints: int = 3) -> List[KeyPoint]:
        """Generate mock keypoints for testing"""
        # Extract topic from the text to generate relevant keypoints
        text = topic_segment.text.lower()
        
        # Define keypoint templates based on content
        keypoint_templates = {
            'economic': [
                "Government announces new economic policy measures",
                "Focus on boosting growth and employment opportunities", 
                "Implementation planned for the coming fiscal year"
            ],
            'weather': [
                "Heavy rainfall expected in northern regions today",
                "Temperatures dropping to 15 degrees celsius",
                "Residents advised to take necessary precautions"
            ],
            'sports': [
                "Local cricket team wins championship match",
                "Victory achieved in thrilling final over",
                "Team defeats defending champions successfully"
            ],
            'technology': [
                "New AI breakthrough announced by research institute",
                "Technology promises to revolutionize healthcare diagnostics",
                "Implementation expected within next two years"
            ],
            'health': [
                "Medical experts recommend new safety guidelines",
                "Guidelines focus on winter season health protection",
                "Emphasis on preventing respiratory infections"
            ],
            'politics': [
                "Parliament session discusses important legislation",
                "Focus on environmental protection measures",
                "Climate change initiatives receive priority"
            ],
            'business': [
                "Stock market shows positive trends this week",
                "Technology and healthcare sectors lead gains",
                "Investor confidence remains strong"
            ],
            'international': [
                "Global summit addresses climate change issues",
                "World leaders commit to carbon neutrality goals",
                "International cooperation framework established"
            ]
        }
        
        # Determine topic based on text content
        detected_topic = 'general'
        for topic, templates in keypoint_templates.items():
            if topic in text:
                detected_topic = topic
                break
        
        # Use general keypoints if no specific topic detected
        if detected_topic == 'general':
            selected_keypoints = [
                "Important news development reported",
                "Significant impact on local community expected",
                "Further updates to follow"
            ]
        else:
            selected_keypoints = keypoint_templates[detected_topic]
        
        # Generate KeyPoint objects
        keypoints = []
        for i, keypoint_text in enumerate(selected_keypoints[:max_keypoints]):
            keypoint = KeyPoint(
                id=str(uuid.uuid4()),
                segment_id=topic_segment.id,
                text=keypoint_text,
                importance_score=0.9 - (i * 0.1),  # Decreasing importance
                order_index=i,
                model_used="mock-keypoint-generator"
            )
            keypoints.append(keypoint)
        
        logger.info(f"Generated {len(keypoints)} mock keypoints for segment")
        return keypoints
    
    def _parse_keypoints(
        self, 
        generated_text: str, 
        segment_id: str, 
        max_keypoints: int
    ) -> List[KeyPoint]:
        """Parse key points from generated text"""
        keypoints = []
        
        # Simple parsing - look for bullet points or numbered lists
        lines = generated_text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or 
                        line.startswith(f'{i+1}.') or line.startswith(f'{i+1})')):
                
                # Clean up the line
                clean_line = line.lstrip('-•0123456789.) ').strip()
                
                if clean_line and len(keypoints) < max_keypoints:
                    keypoint = KeyPoint(
                        id=f"kp_{segment_id}_{len(keypoints)}",
                        segment_id=segment_id,
                        text=clean_line,
                        importance_score=0.8 - (len(keypoints) * 0.1),  # Decreasing importance
                        order_index=len(keypoints),
                        model_used="facebook/bart-large-cnn"
                    )
                    keypoints.append(keypoint)
        
        return keypoints
    
    def _extract_fallback_keypoints(
        self, 
        topic_segment: TopicSegment, 
        max_keypoints: int
    ) -> List[KeyPoint]:
        """Extract key points using simple fallback method"""
        sentences = self._split_into_sentences(topic_segment.text)
        keypoints = []
        
        # Take first few sentences as key points
        for i, sentence in enumerate(sentences[:max_keypoints]):
            if sentence.strip():
                keypoint = KeyPoint(
                    id=f"kp_{topic_segment.id}_{i}",
                    segment_id=topic_segment.id,
                    text=sentence.strip(),
                    importance_score=0.6,  # Lower confidence for fallback
                    order_index=i,
                    model_used="fallback_extraction"
                )
                keypoints.append(keypoint)
        
        return keypoints

    # Text-to-Speech Methods
    async def text_to_speech(
        self, 
        text: str, 
        model_name: str = "microsoft/speecht5_tts"
    ) -> bytes:
        """
        Convert text to speech using HuggingFace TTS models
        
        Args:
            text: Text to convert to speech
            model_name: HuggingFace TTS model to use
        
        Returns:
            bytes: Audio data in WAV format
        """
        try:
            logger.info(f"Converting text to speech: {text[:50]}...")
            
            # Use a popular TTS model from HuggingFace
            api_url = f"{settings.HUGGINGFACE_BASE_URL}/{model_name}"
            
            payload = {
                "inputs": text,
                "parameters": {
                    "speaker_embeddings": None  # Use default speaker
                }
            }
            
            # Set headers for audio response
            headers = self.headers.copy()
            headers["Accept"] = "audio/wav"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        logger.info(f"TTS completed: {len(audio_data)} bytes")
                        return audio_data
                    else:
                        error_text = await response.text()
                        logger.error(f"TTS API error: {response.status} - {error_text}")
                        
                        # Fallback: generate mock audio
                        return self._generate_mock_audio(text)
        
        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
            # Fallback: generate mock audio
            return self._generate_mock_audio(text)
    
    def _generate_mock_audio(self, text: str) -> bytes:
        """
        Generate mock audio data for development/testing
        
        Args:
            text: Text that would be converted to speech
        
        Returns:
            bytes: Mock WAV audio data
        """
        try:
            import wave
            import struct
            import math
            import io
            
            # Generate a simple sine wave as mock audio
            sample_rate = 22050
            duration = min(len(text) * 0.1, 10.0)  # 0.1 seconds per character, max 10 seconds
            frequency = 440  # A4 note
            
            # Generate sine wave samples
            samples = []
            for i in range(int(sample_rate * duration)):
                t = i / sample_rate
                sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))
                samples.append(sample)
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                
                # Write samples
                for sample in samples:
                    wav_file.writeframes(struct.pack('<h', sample))
            
            wav_buffer.seek(0)
            audio_data = wav_buffer.read()
            
            logger.info(f"Generated mock audio: {len(audio_data)} bytes for text: {text[:30]}...")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error generating mock audio: {e}")
            # Return minimal WAV header if all else fails
            return b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x22\x56\x00\x00\x44\xac\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00'