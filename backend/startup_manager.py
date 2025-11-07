"""
Startup Manager - Handles system initialization with proper error handling
"""
import asyncio
import sys
from typing import Dict, Any, List
from loguru import logger
from .core.config_manager import config_manager
from .core.database_manager import DatabaseManager

class StartupManager:
    """Manages system startup with dependency validation and graceful failure handling"""
    
    def __init__(self):
        self.config = None
        self.db_manager = None
        self.startup_status = {}
        
    async def initialize_system(self) -> Dict[str, Any]:
        """Initialize system components with proper error handling"""
        logger.info("Starting system initialization...")
        
        startup_results = {
            "success": False,
            "components": {},
            "errors": [],
            "warnings": []
        }
        
        try:
            # Step 1: Load and validate configuration
            config_result = await self._initialize_configuration()
            startup_results["components"]["configuration"] = config_result
            
            if not config_result["success"]:
                startup_results["errors"].append("Configuration validation failed")
                return startup_results
            
            # Step 2: Initialize database
            db_result = await self._initialize_database()
            startup_results["components"]["database"] = db_result
            
            if not db_result["success"]:
                startup_results["warnings"].append("Database initialization failed - using fallback")
            
            # Step 3: Validate external services
            services_result = await self._validate_services()
            startup_results["components"]["services"] = services_result
            
            # Step 4: Final system check
            system_check = await self._perform_system_check()
            startup_results["components"]["system_check"] = system_check
            
            # Determine overall success
            critical_failures = len([c for c in startup_results["components"].values() 
                                   if not c.get("success", False) and c.get("critical", False)])
            
            startup_results["success"] = critical_failures == 0
            
            if startup_results["success"]:
                logger.info("System initialization completed successfully")
            else:
                logger.warning("System initialization completed with issues")
                
            return startup_results
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            startup_results["errors"].append(f"Critical initialization error: {str(e)}")
            return startup_results
    
    async def _initialize_configuration(self) -> Dict[str, Any]:
        """Initialize and validate configuration"""
        try:
            self.config = config_manager.load_configuration()
            validation = config_manager.validate_configuration()
            
            return {
                "success": validation["valid"],
                "critical": True,
                "details": {
                    "valid": validation["valid"],
                    "issues": validation["issues"],
                    "warnings": validation["warnings"],
                    "development_mode": self.config.development_mode
                }
            }
            
        except Exception as e:
            logger.error(f"Configuration initialization failed: {e}")
            return {
                "success": False,
                "critical": True,
                "error": str(e)
            }
    
    async def _initialize_database(self) -> Dict[str, Any]:
        """Initialize database with fallback handling"""
        try:
            self.db_manager = DatabaseManager()
            success = await self.db_manager.initialize()
            
            if success:
                health = await self.db_manager.health_check()
                return {
                    "success": True,
                    "critical": False,  # Database has fallbacks
                    "details": {
                        "backend": health.get("backend", "unknown"),
                        "status": health.get("status", "unknown")
                    }
                }
            else:
                return {
                    "success": False,
                    "critical": False,
                    "error": "Database initialization failed - fallback will be used"
                }
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return {
                "success": False,
                "critical": False,
                "error": str(e)
            }
    
    async def _validate_services(self) -> Dict[str, Any]:
        """Validate external service availability"""
        try:
            service_status = config_manager.get_service_status()
            
            # Check HuggingFace availability
            hf_available = bool(self.config.huggingface.api_token) if self.config else False
            
            return {
                "success": True,  # Services are optional with fallbacks
                "critical": False,
                "details": {
                    "huggingface": "available" if hf_available else "mock_mode",
                    "kafka": service_status.get("kafka", "disabled"),
                    "real_audio": service_status.get("real_audio", "mock")
                }
            }
            
        except Exception as e:
            logger.error(f"Service validation failed: {e}")
            return {
                "success": False,
                "critical": False,
                "error": str(e)
            }
    
    async def _perform_system_check(self) -> Dict[str, Any]:
        """Perform final system readiness check"""
        try:
            checks = []
            
            # Configuration check
            if self.config:
                checks.append({"name": "configuration", "status": "pass"})
            else:
                checks.append({"name": "configuration", "status": "fail"})
            
            # Database check
            if self.db_manager:
                try:
                    health = await self.db_manager.health_check()
                    status = "pass" if health["status"] in ["healthy", "degraded"] else "fail"
                    checks.append({"name": "database", "status": status})
                except:
                    checks.append({"name": "database", "status": "fail"})
            else:
                checks.append({"name": "database", "status": "fail"})
            
            # API readiness check
            checks.append({"name": "api_ready", "status": "pass"})
            
            failed_checks = [c for c in checks if c["status"] == "fail"]
            
            return {
                "success": len(failed_checks) == 0,
                "critical": False,
                "details": {
                    "checks": checks,
                    "failed_count": len(failed_checks),
                    "ready_for_requests": len(failed_checks) == 0
                }
            }
            
        except Exception as e:
            logger.error(f"System check failed: {e}")
            return {
                "success": False,
                "critical": False,
                "error": str(e)
            }
    
    async def shutdown_system(self):
        """Gracefully shutdown system components"""
        logger.info("Starting system shutdown...")
        
        try:
            if self.db_manager:
                await self.db_manager.close()
                logger.info("Database connections closed")
                
            logger.info("System shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_startup_report(self) -> Dict[str, Any]:
        """Get detailed startup report"""
        return {
            "timestamp": "system_startup",
            "status": self.startup_status,
            "configuration": {
                "loaded": self.config is not None,
                "development_mode": self.config.development_mode if self.config else None
            },
            "database": {
                "initialized": self.db_manager is not None,
                "backend": getattr(self.db_manager, 'current_backend', None) if self.db_manager else None
            }
        }

# Global startup manager instance
startup_manager = StartupManager()