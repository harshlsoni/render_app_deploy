"""
Configuration Manager - Unified configuration system with validation
"""
import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from pydantic import BaseModel, ValidationError, Field
from loguru import logger

class DatabaseConfig(BaseModel):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "news_processing"
    sqlite_fallback: bool = True
    connection_timeout: int = 5000

class APIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    cors_origins: List[str] = ["*"]

class HuggingFaceConfig(BaseModel):
    api_token: str = ""
    base_url: str = "https://router.huggingface.co/hf-inference"
    timeout: int = 30
    max_retries: int = 3

class ProcessingConfig(BaseModel):
    max_audio_length: int = 30
    confidence_threshold: float = 0.7
    max_keypoints: int = 5
    mock_mode: bool = False

class SystemConfig(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    api: APIConfig = APIConfig()
    huggingface: HuggingFaceConfig = HuggingFaceConfig()
    processing: ProcessingConfig = ProcessingConfig()
    
    # Development mode settings
    development_mode: bool = True
    enable_kafka: bool = False
    enable_real_audio: bool = False

class ConfigurationManager:
    """Unified configuration management with validation and environment handling"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or ".env"
        self.config: Optional[SystemConfig] = None
        self._env_vars: Dict[str, str] = {}
        
    def load_configuration(self) -> SystemConfig:
        """Load and validate configuration from environment and files"""
        try:
            # Load environment variables
            self._load_env_file()
            
            # Create configuration with environment overrides
            config_data = self._build_config_dict()
            
            # Validate configuration
            self.config = SystemConfig(**config_data)
            
            # Apply development mode defaults
            if self.config.development_mode:
                self._apply_development_defaults()
            
            logger.info("Configuration loaded and validated successfully")
            return self.config
            
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            # Return safe defaults
            self.config = SystemConfig()
            self._apply_development_defaults()
            return self.config
            
        except Exception as e:
            logger.error(f"Configuration loading failed: {e}")
            self.config = SystemConfig()
            return self.config
    
    def _load_env_file(self):
        """Load environment variables from .env file"""
        env_path = Path(self.config_path)
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            self._env_vars[key.strip()] = value.strip()
            except Exception as e:
                logger.warning(f"Error reading .env file: {e}")
        
        # Also load from actual environment
        self._env_vars.update(os.environ)
    
    def _build_config_dict(self) -> Dict[str, Any]:
        """Build configuration dictionary from environment variables"""
        return {
            "database": {
                "mongodb_url": self._env_vars.get("MONGODB_URL", "mongodb://localhost:27017"),
                "mongodb_database": self._env_vars.get("MONGODB_DATABASE", "news_processing"),
                "sqlite_fallback": self._env_vars.get("SQLITE_FALLBACK", "true").lower() == "true",
                "connection_timeout": int(self._env_vars.get("DB_CONNECTION_TIMEOUT", "5000"))
            },
            "api": {
                "host": self._env_vars.get("API_HOST", "0.0.0.0"),
                "port": int(self._env_vars.get("API_PORT", "8000")),
                "reload": self._env_vars.get("API_RELOAD", "true").lower() == "true",
                "cors_origins": self._env_vars.get("CORS_ORIGINS", "*").split(",")
            },
            "huggingface": {
                "api_token": self._env_vars.get("HUGGINGFACE_API_TOKEN", ""),
                "base_url": self._env_vars.get("HUGGINGFACE_BASE_URL", "https://router.huggingface.co/hf-inference"),
                "timeout": int(self._env_vars.get("HF_TIMEOUT", "30")),
                "max_retries": int(self._env_vars.get("HF_MAX_RETRIES", "3"))
            },
            "processing": {
                "max_audio_length": int(self._env_vars.get("MAX_AUDIO_LENGTH", "30")),
                "confidence_threshold": float(self._env_vars.get("CONFIDENCE_THRESHOLD", "0.7")),
                "max_keypoints": int(self._env_vars.get("MAX_KEYPOINTS", "5")),
                "mock_mode": self._env_vars.get("MOCK_MODE", "false").lower() == "true"
            },
            "development_mode": self._env_vars.get("DEVELOPMENT_MODE", "true").lower() == "true",
            "enable_kafka": self._env_vars.get("ENABLE_KAFKA", "false").lower() == "true",
            "enable_real_audio": self._env_vars.get("ENABLE_REAL_AUDIO", "false").lower() == "true"
        }
    
    def _apply_development_defaults(self):
        """Apply development-friendly defaults"""
        if self.config and self.config.development_mode:
            # Enable mock mode for easier development
            self.config.processing.mock_mode = True
            
            # Disable external services by default in dev mode
            self.config.enable_kafka = False
            self.config.enable_real_audio = False
            
            # Use more permissive settings
            self.config.api.cors_origins = ["*"]
            self.config.database.sqlite_fallback = True
            
            logger.info("Applied development mode defaults")
    
    def get_config(self) -> SystemConfig:
        """Get current configuration"""
        if self.config is None:
            return self.load_configuration()
        return self.config
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration and return status"""
        issues = []
        warnings = []
        
        if not self.config:
            issues.append("No configuration loaded")
            return {"valid": False, "issues": issues, "warnings": warnings}
        
        # Check HuggingFace token
        if not self.config.huggingface.api_token:
            warnings.append("HuggingFace API token not configured - using mock responses")
        
        # Check database configuration
        if "localhost" in self.config.database.mongodb_url and not self.config.database.sqlite_fallback:
            warnings.append("MongoDB configured for localhost without SQLite fallback")
        
        # Check development mode settings
        if self.config.development_mode:
            warnings.append("Running in development mode - some features may be mocked")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "backend_config": {
                "database_backend": "mongodb" if self.config.database.mongodb_url else "sqlite",
                "mock_mode": self.config.processing.mock_mode,
                "development_mode": self.config.development_mode
            }
        }
    
    def get_service_status(self) -> Dict[str, str]:
        """Get expected service availability based on configuration"""
        if not self.config:
            return {"error": "No configuration loaded"}
        
        return {
            "database": "mongodb" if self.config.database.mongodb_url else "sqlite",
            "huggingface": "enabled" if self.config.huggingface.api_token else "mock",
            "kafka": "enabled" if self.config.enable_kafka else "disabled",
            "real_audio": "enabled" if self.config.enable_real_audio else "mock",
            "mode": "development" if self.config.development_mode else "production"
        }

# Global configuration manager instance
config_manager = ConfigurationManager()