# File utility functions
import os
import time
from pathlib import Path

def generate_unique_filename(prefix: str, extension: str) -> str:
    """Generate a unique filename using millisecond timestamp."""
    timestamp = int(time.time() * 1000)
    return f"{prefix}_{timestamp}{extension}"

def cleanup_file(file_path: Path) -> bool:
    """Safely delete a file if it exists."""
    try:
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    except Exception as e:
        print(f"Error cleaning up file {file_path}: {e}")
        return False

def get_file_size_mb(file_path: Path) -> float:
    """Get file size in megabytes."""
    if file_path.exists():
        return file_path.stat().st_size / (1024 * 1024)
    return 0.0

def get_file_size_kb(file_path: Path) -> float:
    """Get file size in kilobytes."""
    if file_path.exists():
        return file_path.stat().st_size / 1024
    return 0.0
