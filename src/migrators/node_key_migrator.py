import shutil
import logging
from pathlib import Path
from core import constants as c

logger = logging.getLogger(__name__)


def migrate_node_key(dry_run: bool = False, reverse: bool = False) -> dict:
    """
    Migrate the node key from the old location to the new location.
    """
    src_path = c.NODE_KEY_FILE if not reverse else c.SNAP_NODE_KEY_FILE
    dest_path = c.SNAP_NODE_KEY_FILE if not reverse else c.NODE_KEY_FILE
    owner = c.SNAP_USER if not reverse else c.USER

    if not src_path.exists():
        logger.info("No node key found to migrate.")
        result = {"success": False, "message": "No node key found to migrate."}
        if dry_run:
            result["dry_run"] = True
        return result
    if dry_run:
        logger.info(f"Dry run: Node key would be migrated from {src_path} to {dest_path}.")
        return {"success": True, "dry_run": True, "message": f"Dry run: Node key would be migrated from {src_path} to {dest_path}."}
    try:
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True)
        shutil.copy(src_path, dest_path)

        logger.info(f"Node key copied from {src_path} to {dest_path}.")
        logger.info(f"Changing ownership of {dest_path} to user: {owner} and group: {owner}.")
        shutil.chown(dest_path, user=owner, group=owner)
        logger.info(f"Changing of ownership of {dest_path} completed.")
        logger.info(f"Node key migrated from {src_path} to {dest_path}.")

        return {"success": True, "message": f"Node key migrated from {src_path} to {dest_path}."}
    except Exception as e:
        logger.error(f"Failed to migrate node key: {e}")
        return {"success": False, "message": f"Failed to migrate node key: {e}"}
