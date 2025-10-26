import shutil
import logging
from pathlib import Path
import core.constants as c

logger = logging.getLogger(__name__)


def migrate_node_key(snap_name: str, dry_run: bool = False, reverse: bool = False) -> dict:
    """
    Migrate the node key from the old location to the new location.
    """

    if not snap_name or snap_name not in c.SNAP_CONFIG:
        message = f"Invalid or missing 'snap-name' parameter for migration operation. The snap-name must be one of the supported applications: {', '.join(c.SNAP_CONFIG.keys())}. Please specify a valid snap name to proceed with the migration."
        logger.error(message)
        raise ValueError(message)

    # Normal migration from legacy to snap
    src_path = c.NODE_KEY_FILE
    dest_path = c.SNAP_CONFIG.get(snap_name).get('node_key_file')
    owner = c.SNAP_USER

    if reverse:
        # If reverse is True, swap the paths
        src_path, dest_path = dest_path, src_path
        owner = c.USER

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
