import os
import json
import hashlib
import time
from dotenv import load_dotenv
from typing import Dict, Any, Optional, Union

# Dictionary to track cache statistics
cache_stats = {
    "hits": 0,
    "misses": 0,
    "saved_requests": 0
}

def load_env():
    """Load environment variables from .env file if present"""
    # Try to load from .env file
    load_dotenv()
    
    # Return a dictionary of environment variables
    return {key: os.getenv(key) for key in ["API_KEY"]}

def get_cache_dir() -> str:
    """Get or create the cache directory"""
    cache_dir = os.path.join(os.path.expanduser("~"), ".gitlens_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def get_cache_file_path(repo_url: str) -> str:
    """Generate a unique cache file path for a repository URL"""
    # Create a hash of the repo URL to use as filename
    url_hash = hashlib.md5(repo_url.encode()).hexdigest()
    return os.path.join(get_cache_dir(), f"{url_hash}.json")

def cache_repository_data(repo_url: str, data: Dict[str, Any]) -> None:
    """
    Cache repository analysis data to disk
    
    Args:
        repo_url: The GitHub repository URL
        data: The repository analysis data to cache
    """
    cache_path = get_cache_file_path(repo_url)
    
    # Create a lightweight version for caching (exclude large file contents)
    cache_data = {
        "repo_url": repo_url,
        "folder_structure": data.get("folder_structure", ""),
        "frameworks": data.get("frameworks", []),
        "additional_info": data.get("additional_info", {}),
        "file_metadata": data.get("file_metadata", {}),
        # Store only paths of analyzed files, not contents
        "file_paths": list(data.get("file_contents", {}).keys()),
        "timestamp": time.time()
    }
    
    try:
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print(f"Warning: Failed to cache repository data: {str(e)}")

def get_cached_repository_data(repo_url: str) -> Optional[Dict[str, Any]]:
    """
    Get cached repository data if available and not expired
    
    Args:
        repo_url: The GitHub repository URL
        
    Returns:
        The cached data or None if not available/expired
    """
    cache_path = get_cache_file_path(repo_url)
    
    # Check if cache file exists
    if not os.path.exists(cache_path):
        cache_stats["misses"] += 1
        return None
    
    try:
        with open(cache_path, 'r') as f:
            cached_data = json.load(f)
            
        # Check if cache is expired (older than 24 hours)
        cache_age = time.time() - cached_data.get("timestamp", 0)
        max_age = 24 * 60 * 60  # 24 hours in seconds
        
        if cache_age > max_age:
            cache_stats["misses"] += 1
            return None
            
        cache_stats["hits"] += 1
        return cached_data
    except Exception as e:
        print(f"Warning: Failed to load cached data: {str(e)}")
        cache_stats["misses"] += 1
        return None

def cache_file_content(file_path: str, content: str) -> None:
    """
    Cache individual file content
    
    Args:
        file_path: The file path within the repository
        content: The file content to cache
    """
    # Create a hash of the file path to use as filename
    path_hash = hashlib.md5(file_path.encode()).hexdigest()
    cache_dir = os.path.join(get_cache_dir(), "files")
    os.makedirs(cache_dir, exist_ok=True)
    
    cache_path = os.path.join(cache_dir, f"{path_hash}.txt")
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        print(f"Warning: Failed to cache file content for {file_path}: {str(e)}")

def get_cached_file_content(file_path: str) -> Optional[str]:
    """
    Get cached file content if available
    
    Args:
        file_path: The file path within the repository
        
    Returns:
        The cached file content or None if not available
    """
    # Create a hash of the file path to use as filename
    path_hash = hashlib.md5(file_path.encode()).hexdigest()
    cache_dir = os.path.join(get_cache_dir(), "files")
    cache_path = os.path.join(cache_dir, f"{path_hash}.txt")
    
    # Check if cache file exists
    if not os.path.exists(cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            content = f.read()
            cache_stats["saved_requests"] += 1
            return content
    except Exception as e:
        print(f"Warning: Failed to load cached file content for {file_path}: {str(e)}")
        return None

def get_cache_stats() -> Dict[str, int]:
    """Get cache usage statistics"""
    return cache_stats
