#!/usr/bin/env python3
# Copyright 2025 Dwellir
# See LICENSE file for licensing details.

"""Data migration utilities for moving Polkadot data to snap common directory."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional
import pwd

logger = logging.getLogger(__name__)


class DataMigrationError(Exception):
    """Base exception for data migration errors."""
    pass


class DataMigrator:
    """Handles migration of Polkadot data from legacy location to snap common directory."""
    
    # Default paths
    LEGACY_DATA_DIR = Path("/home/polkadot/.local/share/polkadot")
    SNAP_COMMON_DIR = Path("/var/snap/polkadot/common/polkadot_base")

    def __init__(self, src_path: Optional[Path] = None, dest_path: Optional[Path] = None, reverse: bool = False):
        """Initialize the data migrator.
        
        Args:
            src_path: Custom source data path (defaults to ~/.local/share/polkadot)
            dest_path: Custom destination data path (defaults to /var/snap/polkadot/common)
        """
        if reverse:
            # If reverse is True, swap the paths
            self.src_path = dest_path or self.SNAP_COMMON_DIR
            self.dest_path = src_path or self.LEGACY_DATA_DIR
        else:
            # Normal migration from legacy to snap
            self.src_path = src_path or self.LEGACY_DATA_DIR
            self.dest_path = dest_path or self.SNAP_COMMON_DIR
        
    def check_migration_needed(self) -> Tuple[bool, str]:
        """Check if migration is needed.
        
        Returns:
            Tuple of (needs_migration: bool, reason: str)
        """
        logger.info(f"Checking if migration is needed from {self.src_path} to {self.dest_path}")
        if not self.src_path.exists():
            return False, f"Source data directory {self.src_path} does not exist"
            
        if not os.listdir(self.src_path):
            return False, f"Source data directory {self.src_path} is empty"
            
        if self.dest_path.exists() and os.listdir(self.dest_path):
            return False, f"Destination data directory {self.dest_path} already contains data"
            
        return True, "Migration needed"
    
    def get_directory_info(self, path: Path) -> dict:
        """Get detailed information about a directory.
        
        Args:
            path: Path to examine
            
        Returns:
            Dictionary with directory information
        """
        if not path.exists():
            return {
                "exists": False,
                "path": str(path),
            }
            
        stat_info = path.stat()
        
        # Check if it's a mount point
        is_mountpoint = path.is_mount()
        
        # Get filesystem type and mount info
        mount_info = self._get_mount_info(path)
        
        # Calculate directory size
        size_bytes = self._calculate_directory_size(path)
        
        return {
            "exists": True,
            "path": str(path),
            "is_mountpoint": is_mountpoint,
            "filesystem": mount_info.get("filesystem", "unknown"),
            "mount_options": mount_info.get("options", []),
            "size_bytes": size_bytes,
            "size_human": self._format_size(size_bytes),
            "owner": pwd.getpwuid(stat_info.st_uid).pw_name,
            "permissions": oct(stat_info.st_mode)[-3:],
            "device": stat_info.st_dev
        }
    
    def _get_mount_info(self, path: Path) -> dict:
        """Get mount information for a path.
        
        Args:
            path: Path to check
            
        Returns:
            Dictionary with mount information
        """
        try:
            # Use findmnt to get mount information
            result = subprocess.run([
                "findmnt", "-n", "-o", "FSTYPE,OPTIONS", str(path)
            ], capture_output=True, text=True, check=True)
            
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                return {
                    "filesystem": parts[0],
                    "options": parts[1].split(",")
                }
        except subprocess.CalledProcessError:
            # Fallback: check /proc/mounts
            try:
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4 and parts[1] == str(path):
                            return {
                                "filesystem": parts[2],
                                "options": parts[3].split(",")
                            }
            except Exception as e:
                logger.warning(f"Failed to get mount info: {e}")
                
        return {}
    
    def _calculate_directory_size(self, path: Path) -> int:
        """Calculate total size of directory contents.
        
        Args:
            path: Directory path
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = Path(dirpath) / filename
                    if filepath.exists():
                        total_size += filepath.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate directory size: {e}")
            
        return total_size
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in human readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Human readable size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f}{unit}"
            size_bytes //= 1024
        return f"{size_bytes:.1f}PB"
    
    def can_use_move(self, source: Path, destination: Path) -> bool:
        """Check if we can use simple move operation.
        
        Args:
            source: Source directory
            destination: Destination directory
            
        Returns:
            True if we can use mv, False if we need rsync
        """
        if not source.exists() or not destination.parent.exists():
            return False
            
        # Check if both paths are on the same filesystem
        source_stat = source.stat()
        dest_parent_stat = destination.parent.stat()
        
        same_device = source_stat.st_dev == dest_parent_stat.st_dev
        
        # If source is a mountpoint, we should use rsync for safety
        source_is_mountpoint = source.is_mount()
        
        logger.info(f"Move analysis: same_device={same_device}, source_mountpoint={source_is_mountpoint}")
        
        return same_device and not source_is_mountpoint
    
    def move_data(self, dry_run: bool = False) -> dict:
        """Move data from legacy location to snap common directory.
        
        Args:
            dry_run: If True, only simulate the operation
            
        Returns:
            Dictionary with operation results
            
        Raises:
            DataMigrationError: If migration fails
        """
        logger.info(f"Starting data migration (dry_run={dry_run})")
        
        # Check if migration is needed
        needs_migration, reason = self.check_migration_needed()
        if not needs_migration:
            return {
                "success": False,
                "method": "none",
                "reason": reason,
                "dry_run": dry_run
            }
        
        # Get directory information
        source_info = self.get_directory_info(self.src_path)
        dest_info = self.get_directory_info(self.dest_path.parent)
        
        logger.info(f"Source info: {source_info}")
        logger.info(f"Destination parent info: {dest_info}")
        
        # Determine migration method
        use_move = self.can_use_move(self.src_path, self.dest_path)
        method = "move" if use_move else "rsync"
        
        logger.info(f"Using migration method: {method}")
        
        if dry_run:
            return {
                "success": True,
                "method": method,
                "source_info": source_info,
                "destination_info": dest_info,
                "dry_run": True,
                "estimated_time": self._estimate_migration_time(source_info["size_bytes"], method)
            }
        
        try:
            # Ensure destination parent exists
            self.dest_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            if use_move:
                result = self._move_with_mv(self.src_path, self.dest_path)
            else:
                result = self._move_with_rsync(self.src_path, self.dest_path)
            
            # Verify migration
            if not self._verify_migration(self.src_path, self.dest_path):
                raise DataMigrationError("Migration verification failed")

            # Ensure permissions and ownership
            if self.dest_path.is_relative_to("/var/snap/polkadot"):
                subprocess.run(["chown", "-R", "root:root", str(self.dest_path)])
            elif self.dest_path.is_relative_to("/home/polkadot/.local/share/polkadot"):
                subprocess.run(["chown", "-R", "polkadot:polkadot", str(self.dest_path)])

            result.update({
                "success": True,
                "method": method,
                "source_info": source_info,
                "destination_info": self.get_directory_info(self.dest_path)
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            raise DataMigrationError(f"Migration failed: {e}")
    
    def _move_with_mv(self, source: Path, destination: Path) -> dict:
        """Move data using mv command (same filesystem).
        
        Args:
            source: Source directory
            destination: Destination directory
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Moving {source} to {destination} using mv")
        
        try:
            # Use shutil.move for atomic operation
            shutil.move(str(source), str(destination))
            
            return {
                "operation": "move",
                "command": f"mv {source} {destination}",
                "atomic": True
            }
            
        except Exception as e:
            raise DataMigrationError(f"Move operation failed: {e}")
    
    def _move_with_rsync(self, source: Path, destination: Path) -> dict:
        """Move data using rsync (cross-filesystem or mounted directory).
        
        Args:
            source: Source directory
            destination: Destination directory
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Moving {source} to {destination} using rsync")
        
        try:
            # Create destination directory
            destination.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Rsync command with progress and preservation of attributes
            rsync_cmd = [
                "rsync",
                "-avP",  # archive, verbose, progress
                "--remove-source-files",  # Remove source files after successful transfer
                f"{source}/",  # Source with trailing slash
                str(destination)
            ]
            
            logger.info(f"Running: {' '.join(rsync_cmd)}")
            
            result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Remove empty source directory structure
            self._remove_empty_dirs(source)
            
            return {
                "operation": "rsync",
                "command": " ".join(rsync_cmd),
                "atomic": False,
                "output": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.CalledProcessError as e:
            raise DataMigrationError(f"Rsync operation failed: {e.stderr}")
    
    def _remove_empty_dirs(self, path: Path) -> None:
        """Remove empty directory structure.
        
        Args:
            path: Root path to clean up
        """
        try:
            # Remove empty directories bottom-up
            for root, dirs, files in os.walk(path, topdown=False):
                root_path = Path(root)
                if not files and not dirs:
                    root_path.rmdir()
                    logger.info(f"Removed empty directory: {root_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up empty directories: {e}")
    
    def _verify_migration(self, source: Path, destination: Path) -> bool:
        """Verify that migration was successful.
        
        Args:
            source: Original source path (should be empty or non-existent)
            destination: Destination path (should contain data)
            
        Returns:
            True if verification passes
        """
        logger.info("Verifying migration...")
        
        # Check that destination exists and has content
        if not destination.exists():
            logger.error("Destination directory does not exist")
            return False
            
        if not os.listdir(destination):
            logger.error("Destination directory is empty")
            return False
        
        # Check that source is empty or doesn't exist
        if source.exists() and os.listdir(source):
            logger.error("Source directory still contains files")
            return False
        
        logger.info("Migration verification passed")
        return True
    
    def _estimate_migration_time(self, size_bytes: int, method: str) -> str:
        """Estimate migration time based on size and method.
        
        Args:
            size_bytes: Size of data to migrate
            method: Migration method (move or rsync)
            
        Returns:
            Estimated time as string
        """
        if method == "move":
            return "< 1 second (atomic operation)"
        
        # Rough estimate for rsync (assuming ~100MB/s)
        estimated_seconds = size_bytes / (100 * 1024 * 1024)
        
        if estimated_seconds < 60:
            return f"~{estimated_seconds:.0f} seconds"
        elif estimated_seconds < 3600:
            return f"~{estimated_seconds/60:.1f} minutes"
        else:
            return f"~{estimated_seconds/3600:.1f} hours"
  
    
def migrate_data(src, dest, dry_run, reverse) -> None:
    """
    Migrate data from src to dest.
    If src is None, the data is not migrated.
    If dest is None, the data is not migrated.
    """
    data_migrator = DataMigrator(
        src_path=Path(src) if src else None,
        dest_path=Path(dest) if dest else None,
        reverse=bool(reverse) if reverse else False,
    )
    return data_migrator.move_data(dry_run=bool(dry_run) if dry_run else False)
