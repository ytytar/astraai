#!/usr/bin/env python3
"""
CLI tool for managing agent configuration backups.
"""

import sys
import os
import argparse
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.backup_utils import (
    backup_agent_config,
    backup_all_agents,
    list_backups,
    restore_agent_from_backup,
    cleanup_old_backups
)


def backup_agent(args):
    """Backup a specific agent."""
    backup_path = backup_agent_config(args.agent_name, args.agents_dir, args.reason or "manual")
    if backup_path:
        print(f"✅ Backup created: {backup_path}")
        return True
    else:
        print(f"❌ Failed to create backup for {args.agent_name}")
        return False


def backup_all(args):
    """Backup all agents."""
    backup_paths = backup_all_agents(args.agents_dir, args.reason or "manual")
    if backup_paths:
        print(f"✅ Created {len(backup_paths)} backups:")
        for path in backup_paths:
            print(f"  - {path}")
        return True
    else:
        print("❌ Failed to create backups")
        return False


def list_all_backups(args):
    """List all available backups."""
    backups = list_backups(args.agents_dir, args.agent_name)
    
    if not backups:
        if args.agent_name:
            print(f"No backups found for agent '{args.agent_name}'")
        else:
            print("No backups found")
        return
    
    print(f"Found {len(backups)} backup(s):")
    print()
    
    current_agent = None
    for backup in backups:
        if backup['agent_name'] != current_agent:
            if current_agent is not None:
                print()
            current_agent = backup['agent_name']
            print(f"Agent: {backup['agent_name']}")
            print("-" * (len(backup['agent_name']) + 7))
        
        created_time = datetime.fromisoformat(backup['created_time']).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {backup['filename']} (reason: {backup['reason']}, created: {created_time})")


def restore_backup(args):
    """Restore agent from backup."""
    if not args.backup_filename:
        print("❌ Backup filename is required for restore")
        return False
    
    backup_filepath = os.path.join(args.agents_dir, "backups", args.backup_filename)
    
    if not os.path.exists(backup_filepath):
        print(f"❌ Backup file not found: {backup_filepath}")
        return False
    
    if restore_agent_from_backup(backup_filepath, args.agents_dir):
        print(f"✅ Successfully restored from backup: {args.backup_filename}")
        return True
    else:
        print(f"❌ Failed to restore from backup: {args.backup_filename}")
        return False


def cleanup_backups(args):
    """Clean up old backup files."""
    cleaned_count = cleanup_old_backups(args.agents_dir, args.keep_count)
    print(f"✅ Cleaned up {cleaned_count} old backup files")


def main():
    parser = argparse.ArgumentParser(description="Agent Configuration Backup Manager")
    parser.add_argument("--agents-dir", default="./agents", help="Agents directory path")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Backup commands
    backup_parser = subparsers.add_parser("backup", help="Create backup")
    backup_parser.add_argument("agent_name", help="Agent name to backup")
    backup_parser.add_argument("--reason", default="manual", help="Reason for backup")
    
    backup_all_parser = subparsers.add_parser("backup-all", help="Backup all agents")
    backup_all_parser.add_argument("--reason", default="manual", help="Reason for backup")
    
    # List commands
    list_parser = subparsers.add_parser("list", help="List backups")
    list_parser.add_argument("--agent-name", help="Filter by agent name")
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup_filename", help="Backup filename to restore from")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old backups")
    cleanup_parser.add_argument("--keep-count", type=int, default=10, help="Number of backups to keep per agent")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "backup":
            backup_agent(args)
        elif args.command == "backup-all":
            backup_all(args)
        elif args.command == "list":
            list_all_backups(args)
        elif args.command == "restore":
            restore_backup(args)
        elif args.command == "cleanup":
            cleanup_backups(args)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
