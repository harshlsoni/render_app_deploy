"""
Configuration settings for the news processing system
"""
import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    
    # Kafka Configuration (optional - not used in simplified version)
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_AUDIO_TOPIC: str = "audio_segments"
    KAFKA_TRANSCRIPTION_TOPIC: str = "transcriptions"
    KAFKA_KEYPOINTS_TOPIC: str = "keypoints"
    KAFKA_GROUP_ID: str = "news_processor_group"
    
    # HuggingFace Configuration
    HUGGINGFACE_API_TOKEN: str = ""
    HUGGINGFACE_BASE_URL: str = "https://router.huggingface.co/hf-inference"
    
    # Model Endpoints
    WHISPER_BASE_MODEL: str = "openai/whisper-base"
    WHISPER_LARGE_MODEL: str = "openai/whisper-large-v3"
    CUSTOM_FINETUNED_MODEL: str = "Hs2077/granite-finetuned-news"
    WAV2VEC2_MODEL: str = "facebook/wav2vec2-base-960h"
    HUBERT_MODEL: str = "facebook/hubert-base-ls960"
    
    # MongoDB Configuration
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "news_processing"
    
    # Processing Configuration
    MAX_AUDIO_LENGTH: int = 30  # seconds
    CONFIDENCE_THRESHOLD: float = 0.7
    MAX_KEYPOINTS: int = 5
    
    # File Storage
    UPLOAD_DIR: str = "uploads"
    TEMP_DIR: str = "temp"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()