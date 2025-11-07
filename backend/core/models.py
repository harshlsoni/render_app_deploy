"""
Core data models for the news processing system
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class ModelType(str, Enum):
    WHISPER_BASE = "whisper-base"
    WHISPER_LARGE = "whisper-large"
    CUSTOM_FINETUNED = "fine-tuned-custom"
    WAV2VEC2 = "wav2vec2"
    HUBERT = "hubert"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class AudioSegment(BaseModel):
    """Raw audio segment from live stream"""
    id: str = Field(..., description="Unique segment identifier")
    audio_url: str = Field(..., description="URL or path to audio file")
    start_time: datetime = Field(..., description="Segment start time")
    end_time: datetime = Field(..., description="Segment end time")
    duration: float = Field(..., description="Duration in seconds")
    source: str = Field(..., description="News source identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Transcription(BaseModel):
    """Transcribed text from audio"""
    id: str = Field(..., description="Unique transcription identifier")
    segment_id: str = Field(..., description="Reference to audio segment")
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Transcription confidence")
    model_used: ModelType = Field(..., description="Model used for transcription")
    processing_time: float = Field(..., description="Processing time in seconds")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TopicSegment(BaseModel):
    """Segmented topic from transcription"""
    id: str = Field(..., description="Unique topic segment identifier")
    transcription_id: str = Field(..., description="Reference to transcription")
    text: str = Field(..., description="Segment text")
    start_index: int = Field(..., description="Start character index")
    end_index: int = Field(..., description="End character index")
    topic_similarity: float = Field(..., description="Similarity score with previous segment")
    embedding: Optional[List[float]] = Field(None, description="Sentence embedding")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class KeyPoint(BaseModel):
    """Generated key point from topic segment"""
    id: str = Field(..., description="Unique key point identifier")
    segment_id: str = Field(..., description="Reference to topic segment")
    text: str = Field(..., description="Key point text")
    importance_score: float = Field(..., ge=0.0, le=1.0, description="Importance score")
    order_index: int = Field(..., description="Order within segment")
    model_used: str = Field(..., description="LLM model used for generation")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class NewsSegmentComplete(BaseModel):
    """Complete processed news segment"""
    id: str = Field(..., description="Unique identifier")
    audio_segment: AudioSegment
    transcription: Transcription
    topic_segments: List[TopicSegment]
    key_points: List[KeyPoint]
    processing_status: ProcessingStatus
    total_processing_time: float = Field(..., description="Total processing time")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Kafka Message Models
class KafkaMessage(BaseModel):
    """Base Kafka message"""
    message_id: str = Field(..., description="Unique message identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = Field(..., description="Message source")

class AudioMessage(KafkaMessage):
    """Audio processing message"""
    audio_segment: AudioSegment

class TranscriptionMessage(KafkaMessage):
    """Transcription processing message"""
    transcription: Transcription

class KeyPointMessage(KafkaMessage):
    """Key point processing message"""
    key_points: List[KeyPoint]
    segment_id: str

# API Request/Response Models
class ProcessAudioRequest(BaseModel):
    """Request to process audio"""
    audio_url: str = Field(..., description="URL to audio file")
    model_type: ModelType = Field(default=ModelType.CUSTOM_FINETUNED)
    source: str = Field(..., description="News source")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ProcessAudioResponse(BaseModel):
    """Response from audio processing"""
    segment_id: str = Field(..., description="Generated segment ID")
    status: ProcessingStatus = Field(..., description="Processing status")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

class GetKeyPointsRequest(BaseModel):
    """Request to get key points"""
    start_time: Optional[datetime] = Field(None, description="Start time filter")
    end_time: Optional[datetime] = Field(None, description="End time filter")
    source: Optional[str] = Field(None, description="News source filter")
    model_type: Optional[ModelType] = Field(None, description="Model type filter")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")

class GetKeyPointsResponse(BaseModel):
    """Response with key points"""
    key_points: List[KeyPoint]
    total_count: int = Field(..., description="Total available results")
    has_more: bool = Field(..., description="Whether more results available")