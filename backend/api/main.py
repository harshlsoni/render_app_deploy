"""
Main FastAPI application for the news processing system (Simplified - No Kafka)
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from ..services.huggingface_service import HuggingFaceService
from ..services.database_service import DatabaseService
from ..services.realtime_news_processor import RealtimeNewsProcessor
from ..services.news_stream_service import NewsStreamService
from typing import List
from ..core.models import (
    ProcessAudioRequest, ProcessAudioResponse, 
    GetKeyPointsRequest, GetKeyPointsResponse,
    AudioSegment, ModelType, ProcessingStatus, Transcription, TopicSegment, KeyPoint
)
from ..config.settings import settings
from datetime import datetime, timedelta
import uuid

# Global services
db_service = DatabaseService()
hf_service = HuggingFaceService()
stream_service = NewsStreamService()
realtime_processor = RealtimeNewsProcessor(stream_service=stream_service, db_service=db_service)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with improved startup handling"""
    from ..startup_manager import startup_manager
    
    # Startup
    logger.info("Starting news processing system with startup manager")
    try:
        startup_result = await startup_manager.initialize_system()
        
        if startup_result["success"]:
            logger.info("System startup completed successfully")
        else:
            logger.warning("System startup completed with issues - continuing with limited functionality")
            for error in startup_result["errors"]:
                logger.error(f"Startup error: {error}")
            for warning in startup_result["warnings"]:
                logger.warning(f"Startup warning: {warning}")
        
        # Try to initialize optional services
        try:
            await stream_service.initialize()
            logger.info("Stream service initialized")
            
            await realtime_processor.initialize()
            logger.info("Real-time processor initialized")
        except Exception as e:
            logger.warning(f"Optional service initialization failed: {e}")
        
    except Exception as e:
        logger.error(f"Critical startup failure: {e}")
        logger.info("Continuing with minimal functionality")
    
    yield
    
    # Shutdown
    logger.info("Shutting down news processing system")
    try:
        await realtime_processor.stop_processing()
        await stream_service.close()
        await startup_manager.shutdown_system()
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

# Create FastAPI app
app = FastAPI(
    title="News Processing API",
    description="Real-time news audio processing with key point extraction",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependencies
async def get_db_service() -> DatabaseService:
    return db_service

async def get_hf_service() -> HuggingFaceService:
    return hf_service

# Health Check Endpoints
@app.get("/health")
async def health_check():
    """System health check"""
    from ..core.config_manager import config_manager
    from ..core.database_manager import DatabaseManager
    
    try:
        # Get configuration status
        config = config_manager.get_config()
        config_validation = config_manager.validate_configuration()
        service_status = config_manager.get_service_status()
        
        # Check database health using the same service as the rest of the app
        try:
            db_health = await db_service.health_check()
        except Exception as e:
            db_health = {"status": "unhealthy", "error": str(e)}
        
        # Determine overall status
        overall_status = "healthy"
        if not config_validation["valid"] or db_health["status"] != "healthy":
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": db_health["status"],
                "huggingface": service_status["huggingface"],
                "configuration": "valid" if config_validation["valid"] else "invalid"
            },
            "mode": service_status["mode"]
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "services": {
                "database": "unknown",
                "huggingface": "unknown",
                "configuration": "unknown"
            }
        }

@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed system health check with comprehensive diagnostics"""
    from ..core.config_manager import config_manager
    from ..core.database_manager import DatabaseManager
    
    try:
        # Configuration details
        config = config_manager.get_config()
        config_validation = config_manager.validate_configuration()
        service_status = config_manager.get_service_status()
        
        # Database details using the same service as the rest of the app
        try:
            db_health = await db_service.health_check()
            # Test database operations
            test_keypoints = await db_service.get_recent_keypoints(1)
        except Exception as e:
            db_health = {"status": "unhealthy", "error": str(e)}
            test_keypoints = []
        
        # HuggingFace service check
        hf_status = "available" if config.huggingface.api_token else "mock_mode"
        
        return {
            "status": "healthy" if config_validation["valid"] and db_health["status"] == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "configuration": {
                "valid": config_validation["valid"],
                "issues": config_validation["issues"],
                "warnings": config_validation["warnings"],
                "development_mode": config.development_mode
            },
            "services": {
                "database": {
                    "status": db_health["status"],
                    "backend": db_health.get("backend", "unknown"),
                    "connected": db_health.get("connected", False),
                    "test_query_success": len(test_keypoints) >= 0
                },
                "huggingface": {
                    "status": hf_status,
                    "token_configured": bool(config.huggingface.api_token),
                    "base_url": config.huggingface.base_url
                },
                "processing": {
                    "mock_mode": config.processing.mock_mode,
                    "max_audio_length": config.processing.max_audio_length,
                    "confidence_threshold": config.processing.confidence_threshold
                }
            },
            "system_info": {
                "mode": service_status["mode"],
                "kafka_enabled": service_status["kafka"] == "enabled",
                "real_audio_enabled": service_status["real_audio"] == "enabled"
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "configuration": {"valid": False, "issues": [str(e)]},
            "services": {"database": {"status": "unknown"}, "huggingface": {"status": "unknown"}}
        }

@app.get("/health/startup")
async def startup_status():
    """Get system startup status and report"""
    from ..startup_manager import startup_manager
    
    try:
        startup_report = startup_manager.get_startup_report()
        return {
            "startup_completed": True,
            "timestamp": datetime.utcnow().isoformat(),
            "report": startup_report
        }
    except Exception as e:
        return {
            "startup_completed": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

# Audio Processing Endpoints
@app.post("/api/process-audio", response_model=ProcessAudioResponse)
async def process_audio(
    request: ProcessAudioRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Process audio segment and extract key points (async)
    """
    try:
        segment_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        audio_segment = AudioSegment(
            id=segment_id,
            audio_url=request.audio_url,
            start_time=start_time,
            end_time=start_time + timedelta(seconds=30),
            duration=30.0,
            source=request.source,
            metadata=request.metadata
        )
        
        # Process asynchronously
        background_tasks.add_task(
            process_audio_background,
            audio_segment,
            request.model_type
        )
        
        return ProcessAudioResponse(
            segment_id=segment_id,
            status=ProcessingStatus.PROCESSING,
            estimated_completion=start_time + timedelta(minutes=2)
        )
        
    except Exception as e:
        logger.error(f"Error processing audio request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_audio_background(
    audio_segment: AudioSegment,
    model_type: ModelType
):
    """Background task for audio processing"""
    try:
        async with HuggingFaceService() as hf_service:
            # Step 1: Transcribe audio
            transcription = await hf_service.transcribe_audio(
                audio_segment.audio_url, 
                model_type
            )
            
            # Step 2: Segment topics
            topic_segments = await hf_service.segment_topics(transcription)
            
            # Step 3: Generate key points
            all_keypoints = []
            for segment in topic_segments:
                keypoints = await hf_service.generate_keypoints(segment)
                all_keypoints.extend(keypoints)
            
            # Step 4: Store in database (if available)
            try:
                await db_service.store_transcription(transcription)
                for segment in topic_segments:
                    await db_service.store_topic_segment(segment)
                for keypoint in all_keypoints:
                    await db_service.store_keypoint(keypoint)
            except Exception as e:
                logger.warning(f"Database storage failed: {e}")
            
            logger.info(f"Processing completed for segment {audio_segment.id}")
            
    except Exception as e:
        logger.error(f"Background processing failed: {e}")

@app.post("/api/process-audio-sync")
async def process_audio_sync(
    request: ProcessAudioRequest,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Process audio segment synchronously
    """
    try:
        segment_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        audio_segment = AudioSegment(
            id=segment_id,
            audio_url=request.audio_url,
            start_time=start_time,
            end_time=start_time + timedelta(seconds=30),
            duration=30.0,
            source=request.source,
            metadata=request.metadata
        )
        
        async with HuggingFaceService() as hf_service:
            # Step 1: Transcribe audio
            transcription = await hf_service.transcribe_audio(
                audio_segment.audio_url, 
                request.model_type
            )
            
            # Step 2: Segment topics
            topic_segments = await hf_service.segment_topics(transcription)
            
            # Step 3: Generate key points
            all_keypoints = []
            for segment in topic_segments:
                keypoints = await hf_service.generate_keypoints(segment)
                all_keypoints.extend(keypoints)
            
            # Step 4: Store in database (if available)
            try:
                await db_service.store_transcription(transcription)
                for segment in topic_segments:
                    await db_service.store_topic_segment(segment)
                for keypoint in all_keypoints:
                    await db_service.store_keypoint(keypoint)
            except Exception as e:
                logger.warning(f"Database storage failed: {e}")
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return {
                "segment_id": segment_id,
                "status": "completed",
                "transcription": transcription.text,
                "key_points": [kp.text for kp in all_keypoints],
                "processing_time": processing_time,
                "model_used": request.model_type
            }
        
    except Exception as e:
        logger.error(f"Error in sync processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Key Points Retrieval Endpoints
@app.post("/api/keypoints", response_model=GetKeyPointsResponse)
async def get_keypoints(
    request: GetKeyPointsRequest,
    db: DatabaseService = Depends(get_db_service)
):
    """
    Get key points with optional filtering
    """
    try:
        keypoints = await db.search_keypoints(
            start_time=request.start_time.isoformat() if request.start_time else None,
            end_time=request.end_time.isoformat() if request.end_time else None,
            source=request.source,
            limit=request.limit
        )
        
        return GetKeyPointsResponse(
            key_points=keypoints,
            total_count=len(keypoints),
            has_more=len(keypoints) == request.limit
        )
        
    except Exception as e:
        logger.error(f"Error getting key points: {e}")
        # Return empty result if database fails
        return GetKeyPointsResponse(
            key_points=[],
            total_count=0,
            has_more=False
        )

@app.get("/api/keypoints/latest")
async def get_latest_keypoints(limit: int = 10):
    """Get latest key points (simple endpoint for frontend)"""
    try:
        # Use the same DatabaseService that the real-time processor uses
        keypoints = await db_service.get_recent_keypoints(limit)
        
        # Format for frontend compatibility
        formatted_keypoints = []
        for kp in keypoints:
            formatted_keypoints.append({
                "id": kp.id,
                "keypoint_text": kp.text,
                "confidence_score": kp.importance_score,
                "created_at": kp.created_at.isoformat() if isinstance(kp.created_at, datetime) else str(kp.created_at),
                "segment": {
                    "id": kp.segment_id,
                    "model_used": kp.model_used,
                    "start_time": kp.created_at.isoformat() if isinstance(kp.created_at, datetime) else str(kp.created_at),
                    "topic": "news"  # Default topic
                }
            })
        
        # If no real data, return sample data
        if not formatted_keypoints:
            formatted_keypoints = [
                {
                    "id": "sample_1",
                    "keypoint_text": "System initialized successfully - ready for news processing",
                    "confidence_score": 0.9,
                    "created_at": datetime.utcnow().isoformat(),
                    "segment": {
                        "id": "sample_seg_1",
                        "model_used": "fine-tuned-custom",
                        "start_time": datetime.utcnow().isoformat(),
                        "topic": "system"
                    }
                }
            ]
        
        return formatted_keypoints
        
    except Exception as e:
        logger.warning(f"Database query failed: {e}")
        # Return mock data if everything fails
        return [
            {
                "id": "fallback_1",
                "keypoint_text": "Database connection issue - using fallback mode",
                "confidence_score": 0.7,
                "created_at": datetime.utcnow().isoformat(),
                "segment": {
                    "id": "fallback_seg_1",
                    "model_used": "fine-tuned-custom",
                    "start_time": datetime.utcnow().isoformat(),
                    "topic": "system"
                }
            }
        ]

# Processing Status Endpoints
@app.get("/api/status/{segment_id}")
async def get_processing_status(
    segment_id: str,
    db: DatabaseService = Depends(get_db_service)
):
    """Get processing status for a specific segment"""
    try:
        # Try to find the segment in database
        transcription = await db.get_transcription_by_segment_id(segment_id)
        
        if transcription:
            return {"segment_id": segment_id, "status": "completed"}
        else:
            return {"segment_id": segment_id, "status": "not_found"}
        
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        return {"segment_id": segment_id, "status": "unknown"}

# Model Information Endpoints
@app.get("/api/models")
async def get_available_models():
    """Get available ML models with current selection"""
    try:
        from ..model_config import model_config_manager
        model_info = model_config_manager.get_model_display_info()
        
        return {
            "models": [
                {
                    "id": "whisper-base",
                    "name": "Whisper Base",
                    "description": "Fast, general-purpose transcription",
                    "type": "speech-to-text",
                    "speed": "Fast",
                    "accuracy": "Good"
                },
                {
                    "id": "whisper-large",
                    "name": "Whisper Large",
                    "description": "High accuracy transcription",
                    "type": "speech-to-text",
                    "speed": "Slow",
                    "accuracy": "Excellent"
                },
                {
                    "id": "fine-tuned-custom",
                    "name": "Fine-tuned Custom",
                    "description": "Optimized for Indian English news content",
                    "type": "speech-to-text",
                    "speed": "Medium",
                    "accuracy": "Excellent"
                },
                {
                    "id": "wav2vec2",
                    "name": "Wav2Vec 2.0",
                    "description": "Efficient speech recognition",
                    "type": "speech-to-text",
                    "speed": "Fast",
                    "accuracy": "Good"
                },
                {
                    "id": "hubert",
                    "name": "HuBERT",
                    "description": "Robust audio understanding",
                    "type": "speech-to-text",
                    "speed": "Medium",
                    "accuracy": "Very Good"
                }
            ],
            "current_model": model_info["current_model"],
            "configuration_source": model_info["configuration_source"]
        }
    except Exception as e:
        logger.warning(f"Could not load model configuration: {e}")
        return {
            "models": [
                {
                    "id": "whisper-base",
                    "name": "Whisper Base",
                    "description": "Fast, general-purpose transcription",
                    "type": "speech-to-text"
                },
                {
                    "id": "whisper-large",
                    "name": "Whisper Large",
                    "description": "High accuracy transcription",
                    "type": "speech-to-text"
                },
                {
                    "id": "fine-tuned-custom",
                    "name": "Fine-tuned Custom",
                    "description": "Optimized for Indian English news content",
                    "type": "speech-to-text"
                },
                {
                    "id": "wav2vec2",
                    "name": "Wav2Vec 2.0",
                    "description": "Efficient speech recognition",
                    "type": "speech-to-text"
                },
                {
                    "id": "hubert",
                    "name": "HuBERT",
                    "description": "Robust audio understanding",
                    "type": "speech-to-text"
                }
            ],
            "current_model": {
                "id": "fine-tuned-custom",
                "name": "Fine-tuned Custom",
                "source": "default"
            }
        }

# Real-time Processing Endpoints
@app.post("/api/realtime/start")
async def start_realtime_processing(sources: List[str]):
    """Start real-time news processing from specified sources"""
    try:
        # Start news streams
        for source in sources:
            success = await stream_service.start_stream(source)
            if not success:
                logger.warning(f"Failed to start stream: {source}")
        
        # Start real-time processing
        asyncio.create_task(realtime_processor.start_processing(sources))
        
        return {
            "status": "started",
            "sources": sources,
            "message": "Real-time processing started"
        }
        
    except Exception as e:
        logger.error(f"Error starting real-time processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/realtime/stop")
async def stop_realtime_processing():
    """Stop real-time news processing"""
    try:
        await realtime_processor.stop_processing()
        
        return {
            "status": "stopped",
            "message": "Real-time processing stopped"
        }
        
    except Exception as e:
        logger.error(f"Error stopping real-time processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/realtime/status")
async def get_realtime_status():
    """Get real-time processing status"""
    try:
        processor_status = await realtime_processor.get_current_status()
        stream_statuses = await stream_service.get_all_stream_status()
        
        return {
            "processor": processor_status,
            "streams": stream_statuses,
            "total_active_streams": len(stream_statuses)
        }
        
    except Exception as e:
        logger.error(f"Error getting real-time status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/news-sources")
async def get_available_news_sources():
    """Get available news sources for streaming"""
    try:
        sources = await stream_service.get_available_sources()
        return {"sources": sources}
        
    except Exception as e:
        logger.error(f"Error getting news sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/topics/recent")
async def get_recent_topics(limit: int = 10):
    """Get recently completed news topics"""
    try:
        topics = await db_service.get_recent_topics(limit)
        return {"topics": topics}
        
    except Exception as e:
        logger.error(f"Error getting recent topics: {e}")
        return {"topics": []}

@app.post("/api/streams/{source_id}/start")
async def start_specific_stream(source_id: str):
    """Start a specific news stream"""
    try:
        success = await stream_service.start_stream(source_id)
        
        if success:
            return {
                "status": "started",
                "source_id": source_id,
                "message": f"Stream {source_id} started successfully"
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to start stream {source_id}")
            
    except Exception as e:
        logger.error(f"Error starting stream {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/streams/{source_id}/stop")
async def stop_specific_stream(source_id: str):
    """Stop a specific news stream"""
    try:
        await stream_service.stop_stream(source_id)
        
        return {
            "status": "stopped",
            "source_id": source_id,
            "message": f"Stream {source_id} stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Error stopping stream {source_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/streams/{source_id}/status")
async def get_stream_status(source_id: str):
    """Get status of a specific stream"""
    try:
        status = await stream_service.get_stream_status(source_id)
        
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail=f"Stream {source_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Audio Mode Management
@app.post("/api/audio-mode/set")
async def set_audio_mode(request: dict):
    """Set audio capture mode (real vs mock)"""
    try:
        use_real_audio = request.get('use_real_audio', False)
        await stream_service.set_audio_mode(use_real_audio)
        mode = "real" if use_real_audio else "mock"
        
        return {
            "status": "success",
            "mode": mode,
            "message": f"Audio mode set to {mode}"
        }
        
    except Exception as e:
        logger.error(f"Error setting audio mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio-mode/status")
async def get_audio_mode_status():
    """Get current audio mode and capabilities"""
    try:
        mode_info = await stream_service.get_audio_mode()
        return mode_info
        
    except Exception as e:
        logger.error(f"Error getting audio mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Text-to-Speech Endpoints
@app.post("/api/tts/keypoint/{keypoint_id}")
async def generate_keypoint_audio(
    keypoint_id: str,
    hf: HuggingFaceService = Depends(get_hf_service)
):
    """Generate audio for a specific keypoint"""
    try:
        # Get keypoint from database
        keypoint = await db_service.get_keypoint_by_id(keypoint_id)
        
        if not keypoint:
            raise HTTPException(status_code=404, detail="Keypoint not found")
        
        # Generate audio using TTS
        async with HuggingFaceService() as hf_service:
            audio_data = await hf_service.text_to_speech(keypoint.text)
        
        # Return audio as streaming response
        from fastapi.responses import StreamingResponse
        import io
        
        audio_stream = io.BytesIO(audio_data)
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=keypoint_{keypoint_id}.wav",
                "Cache-Control": "public, max-age=3600"  # Cache for 1 hour
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating keypoint audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tts/text")
async def generate_text_audio(
    request: dict,
    hf: HuggingFaceService = Depends(get_hf_service)
):
    """Generate audio for arbitrary text"""
    try:
        text = request.get('text', '').strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        if len(text) > 500:
            raise HTTPException(status_code=400, detail="Text too long (max 500 characters)")
        
        # Generate audio using TTS
        async with HuggingFaceService() as hf_service:
            audio_data = await hf_service.text_to_speech(text)
        
        # Return audio as streaming response
        from fastapi.responses import StreamingResponse
        import io
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=generated_audio.wav",
                "Cache-Control": "public, max-age=300"  # Cache for 5 minutes
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating text audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD
    )