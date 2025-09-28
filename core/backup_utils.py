"""
Backup utilities for agent configurations.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


def create_backup_dir(agents_dir: str) -> str:
    """
    Create backup directory if it doesn't exist.
    
    Args:
        agents_dir: Base agents directory
        
    Returns:
        Path to backup directory
    """
    backup_dir = os.path.join(agents_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def backup_agent_config(agent_name: str, agents_dir: str, backup_reason: str = "update") -> Optional[str]:
    """
    Create a timestamped backup of an agent configuration.
    
    Args:
        agent_name: Name of the agent to backup
        agents_dir: Directory containing agent configurations
        backup_reason: Reason for backup (update, delete, etc.)
        
    Returns:
        Path to backup file if successful, None otherwise
    """
    try:
        source_file = os.path.join(agents_dir, f"{agent_name}.yaml")
        
        if not os.path.exists(source_file):
            logger.warning(f"Agent config file not found: {source_file}")
            return None
        
        backup_dir = create_backup_dir(agents_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{agent_name}_{backup_reason}_{timestamp}.yaml"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        shutil.copy2(source_file, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path
        
    except Exception as e:
        logger.error(f"Failed to create backup for {agent_name}: {e}")
        return None


def backup_all_agents(agents_dir: str, backup_reason: str = "bulk_backup") -> List[str]:
    """
    Create backups for all agent configurations.
    
    Args:
        agents_dir: Directory containing agent configurations
        backup_reason: Reason for backup
        
    Returns:
        List of backup file paths
    """
    backup_paths = []
    
    try:
        for file in os.listdir(agents_dir):
            if file.endswith(".yaml") and not file.startswith("config.example"):
                agent_name = file.replace(".yaml", "")
                backup_path = backup_agent_config(agent_name, agents_dir, backup_reason)
                if backup_path:
                    backup_paths.append(backup_path)
    except Exception as e:
        logger.error(f"Failed to backup all agents: {e}")
    
    return backup_paths


def list_backups(agents_dir: str, agent_name: Optional[str] = None) -> List[dict]:
    """
    List available backups.
    
    Args:
        agents_dir: Directory containing agent configurations
        agent_name: Optional specific agent name to filter backups
        
    Returns:
        List of backup information dictionaries
    """
    backup_dir = os.path.join(agents_dir, "backups")
    backups = []
    
    if not os.path.exists(backup_dir):
        return backups
    
    try:
        for file in os.listdir(backup_dir):
            if file.endswith(".yaml"):
                parts = file.replace(".yaml", "").split("_")
                if len(parts) >= 3:
                    backup_agent_name = parts[0]
                    backup_reason = parts[1]
                    backup_timestamp = "_".join(parts[2:])
                    
                    if agent_name is None or backup_agent_name == agent_name:
                        backup_info = {
                            "agent_name": backup_agent_name,
                            "reason": backup_reason,
                            "timestamp": backup_timestamp,
                            "filename": file,
                            "filepath": os.path.join(backup_dir, file),
                            "created_time": datetime.fromtimestamp(
                                os.path.getctime(os.path.join(backup_dir, file))
                            ).isoformat()
                        }
                        backups.append(backup_info)
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")
    
    # Sort by creation time, newest first
    backups.sort(key=lambda x: x["created_time"], reverse=True)
    return backups


def restore_agent_from_backup(backup_filepath: str, agents_dir: str) -> bool:
    """
    Restore an agent configuration from a backup.
    
    Args:
        backup_filepath: Path to backup file
        agents_dir: Directory containing agent configurations
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(backup_filepath):
            logger.error(f"Backup file not found: {backup_filepath}")
            return False
        
        # Extract agent name from backup filename
        backup_filename = os.path.basename(backup_filepath)
        agent_name = backup_filename.split("_")[0]
        
        # Create backup of current config before restore
        current_backup = backup_agent_config(agent_name, agents_dir, "pre_restore")
        if current_backup:
            logger.info(f"Created pre-restore backup: {current_backup}")
        
        # Restore from backup
        target_file = os.path.join(agents_dir, f"{agent_name}.yaml")
        shutil.copy2(backup_filepath, target_file)
        logger.info(f"Restored {agent_name} from backup: {backup_filepath}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore from backup {backup_filepath}: {e}")
        return False


def cleanup_old_backups(agents_dir: str, keep_count: int = 10) -> int:
    """
    Clean up old backup files, keeping only the most recent ones per agent.
    
    Args:
        agents_dir: Directory containing agent configurations
        keep_count: Number of backups to keep per agent
        
    Returns:
        Number of files cleaned up
    """
    backup_dir = os.path.join(agents_dir, "backups")
    if not os.path.exists(backup_dir):
        return 0
    
    cleaned_count = 0
    
    try:
        # Group backups by agent name
        agent_backups = {}
        for file in os.listdir(backup_dir):
            if file.endswith(".yaml"):
                agent_name = file.split("_")[0]
                if agent_name not in agent_backups:
                    agent_backups[agent_name] = []
                
                filepath = os.path.join(backup_dir, file)
                agent_backups[agent_name].append({
                    "file": file,
                    "path": filepath,
                    "mtime": os.path.getmtime(filepath)
                })
        
        # Clean up old backups for each agent
        for agent_name, backups in agent_backups.items():
            # Sort by modification time, newest first
            backups.sort(key=lambda x: x["mtime"], reverse=True)
            
            # Remove old backups beyond keep_count
            for backup in backups[keep_count:]:
                try:
                    os.remove(backup["path"])
                    logger.info(f"Cleaned up old backup: {backup['file']}")
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"Failed to remove backup {backup['file']}: {e}")
                    
    except Exception as e:
        logger.error(f"Failed to cleanup old backups: {e}")
    
    return cleaned_count
