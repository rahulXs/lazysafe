"""backup and restore for apply operations."""

import shutil
import time


def _run_id():
    return time.strftime("%Y%m%dT%H%M%S")


def backup_dir(base):
    return base / ".lazysafe" / "backup"


def create_backup(plan, project_root):
    run_id = _run_id()
    dest = backup_dir(project_root) / run_id
    dest.mkdir(parents=True, exist_ok=True)

    for change in plan.changes:
        rel = change.path.relative_to(project_root)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(change.path, target)

    return dest


def restore(backup_path, plan, project_root):
    for change in plan.changes:
        rel = change.path.relative_to(project_root)
        src = backup_path / rel
        if src.exists():
            shutil.copy2(src, change.path)
