"""
Backup API endpoints for FastAPI application.
This module provides backup functionality for agent configurations.
"""

import os
from fastapi import FastAPI, HTTPException, Request
from typing import Dict, Any
from google.adk.cli.utils.agent_loader import AgentLoader

from .backup_utils import (
    backup_agent_config,
    backup_all_agents,
    list_backups,
    restore_agent_from_backup,
    cleanup_old_backups
)


def enhance_app_with_backup_endpoints(app: FastAPI, agent_loader: AgentLoader) -> FastAPI:
    """
    Enhance FastAPI app with backup management endpoints.
    
    Args:
        app: FastAPI application instance
        agent_loader: Agent loader instance
        
    Returns:
        Enhanced FastAPI application
    """

    @app.post(
        "/agents/backup",
        tags=["backup"],
        summary="Backup all agent configurations"
    )
    async def backup_all_agent_configs() -> Dict[str, Any]:
        """Create backups for all agent configurations."""
        try:
            backup_paths = backup_all_agents(agent_loader.agents_dir, "manual_backup")
            return {
                "message": f"Created {len(backup_paths)} backups",
                "backups": backup_paths,
                "status": "success"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create backups: {str(e)}")

    @app.post(
        "/agents/{agent_name}/backup",
        tags=["backup"],
        summary="Backup specific agent configuration"
    )
    async def backup_agent(agent_name: str) -> Dict[str, Any]:
        """Create backup for a specific agent configuration."""
        agents_list = list(agent_loader.list_agents())
        if agent_name not in agents_list:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        try:
            backup_path = backup_agent_config(agent_name, agent_loader.agents_dir, "manual_backup")
            if not backup_path:
                raise HTTPException(status_code=500, detail="Failed to create backup")
            
            return {
                "message": f"Backup created for agent {agent_name}",
                "backup_path": backup_path,
                "agent_name": agent_name,
                "status": "success"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create backup: {str(e)}")

    @app.get(
        "/agents/backups",
        tags=["backup"],
        summary="List all available backups"
    )
    async def get_all_backups() -> Dict[str, Any]:
        """List all available backups."""
        try:
            backups = list_backups(agent_loader.agents_dir)
            return {
                "backups": backups,
                "count": len(backups),
                "status": "success"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")

    @app.get(
        "/agents/{agent_name}/backups",
        tags=["backup"],
        summary="List backups for specific agent"
    )
    async def get_agent_backups(agent_name: str) -> Dict[str, Any]:
        """List backups for a specific agent."""
        try:
            backups = list_backups(agent_loader.agents_dir, agent_name)
            return {
                "agent_name": agent_name,
                "backups": backups,
                "count": len(backups),
                "status": "success"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")

    @app.post(
        "/agents/{agent_name}/restore",
        tags=["backup"],
        summary="Restore agent from backup"
    )
    async def restore_agent(agent_name: str, request: Request) -> Dict[str, Any]:
        """Restore agent from a backup."""
        try:
            data = await request.json()
            backup_filename = data.get("backup_filename")
            if not backup_filename:
                raise HTTPException(status_code=400, detail="backup_filename is required")
            
            backup_filepath = os.path.join(agent_loader.agents_dir, "backups", backup_filename)
            
            if not os.path.exists(backup_filepath):
                raise HTTPException(status_code=404, detail="Backup file not found")
            
            if restore_agent_from_backup(backup_filepath, agent_loader.agents_dir):
                return {
                    "message": f"Agent {agent_name} restored from backup {backup_filename}",
                    "agent_name": agent_name,
                    "backup_filename": backup_filename,
                    "status": "success"
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to restore from backup")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to restore agent: {str(e)}")

    @app.delete(
        "/agents/backups/cleanup",
        tags=["backup"],
        summary="Clean up old backup files"
    )
    async def cleanup_backups(keep_count: int = 10) -> Dict[str, Any]:
        """Clean up old backup files, keeping only the most recent ones per agent."""
        try:
            if keep_count < 1:
                raise HTTPException(status_code=400, detail="keep_count must be at least 1")
            
            cleaned_count = cleanup_old_backups(agent_loader.agents_dir, keep_count)
            return {
                "message": f"Cleaned up {cleaned_count} old backup files",
                "cleaned_count": cleaned_count,
                "keep_count": keep_count,
                "status": "success"
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to cleanup backups: {str(e)}")

    @app.get(
        "/agents/backups/stats",
        tags=["backup"],
        summary="Get backup statistics"
    )
    async def get_backup_stats() -> Dict[str, Any]:
        """Get statistics about backups."""
        try:
            all_backups = list_backups(agent_loader.agents_dir)
            
            # Group by agent
            agent_stats = {}
            total_size = 0
            
            for backup in all_backups:
                agent_name = backup["agent_name"]
                if agent_name not in agent_stats:
                    agent_stats[agent_name] = {
                        "count": 0,
                        "latest_backup": None,
                        "oldest_backup": None
                    }
                
                agent_stats[agent_name]["count"] += 1
                
                # Update latest/oldest
                backup_time = backup["created_time"]
                if (agent_stats[agent_name]["latest_backup"] is None or 
                    backup_time > agent_stats[agent_name]["latest_backup"]):
                    agent_stats[agent_name]["latest_backup"] = backup_time
                
                if (agent_stats[agent_name]["oldest_backup"] is None or 
                    backup_time < agent_stats[agent_name]["oldest_backup"]):
                    agent_stats[agent_name]["oldest_backup"] = backup_time
                
                # Calculate file size if possible
                try:
                    file_size = os.path.getsize(backup["filepath"])
                    total_size += file_size
                except:
                    pass
            
            return {
                "total_backups": len(all_backups),
                "total_agents_with_backups": len(agent_stats),
                "total_size_bytes": total_size,
                "agent_stats": agent_stats,
                "status": "success"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get backup stats: {str(e)}")

    return app


def create_backup_before_update(agent_name: str, agent_loader: AgentLoader, reason: str = "update") -> str:
    """
    Create a backup before updating an agent configuration.
    
    Args:
        agent_name: Name of the agent
        agent_loader: Agent loader instance
        reason: Reason for the backup
        
    Returns:
        Path to the created backup file
        
    Raises:
        HTTPException: If backup creation fails
    """
    backup_path = backup_agent_config(agent_name, agent_loader.agents_dir, reason)
    if not backup_path:
        raise HTTPException(status_code=500, detail="Failed to create backup before update")
    return backup_path
