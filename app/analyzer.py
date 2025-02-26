# app/enhanced_analyzer.py
import re
import requests
import time
import os
import sys
import base64
import chardet
from urllib.parse import urlparse

# Simple caching mechanism to reduce API calls
repo_cache = {}
file_content_cache = {}


def analyze_repo(repo_url: str, github_token: str = None, max_file_size: int = 500000, file_limit: int = 100) -> dict:
    """
    Analyze a GitHub repository and extract folder structure, frameworks used, and file contents.

    Args:
        repo_url (str): URL of the GitHub repository to analyze
        github_token (str, optional): GitHub personal access token for authentication
        max_file_size (int): Maximum file size to read (bytes)
        file_limit (int): Maximum number of files to analyze deeply

    Returns:
        dict: Analysis results including folder structure, frameworks and file contents
    """
    # Check if this repo is in the persistent cache
    from app.utils import get_cached_repository_data, cache_repository_data, cache_file_content, get_cached_file_content
    
    cached_data = get_cached_repository_data(repo_url)
    if cached_data:
        print(f"Using cached analysis for {repo_url}")
        
        # For cached data, we need to load file contents separately
        folder_structure = cached_data.get("folder_structure", "")
        frameworks = cached_data.get("frameworks", [])
        file_paths = cached_data.get("file_paths", [])
        
        # Fetch file contents from cache
        file_contents = {}
        for path in file_paths:
            content = get_cached_file_content(path)
            if content:
                file_contents[path] = content
                
        # Build response similar to a full analysis
        return {
            "folder_structure": folder_structure,
            "frameworks": frameworks,
            "file_contents": file_contents,
            "file_metadata": cached_data.get("file_metadata", {}),
            "additional_info": cached_data.get("additional_info", {})
        }
    
    # Check if this repo is in the in-memory cache
    if repo_url in repo_cache:
        print(f"Using in-memory cached analysis for {repo_url}")
        return repo_cache[repo_url]

    # Parse the GitHub URL to extract owner and repo name
    parsed_url = urlparse(repo_url)
    path_parts = parsed_url.path.strip("/").split("/")

    if len(path_parts) < 2:
        raise ValueError(
            "Invalid GitHub repository URL. Expected format: https://github.com/owner/repo"
        )

    owner = path_parts[0]
    repo = path_parts[1]

    # Set up API request headers
    headers = {"Accept": "application/vnd.github.v3+json"}

    # Add authentication if token is provided
    if github_token:
        headers["Authorization"] = f"token {github_token}"
        print("Using GitHub authentication for API requests")

    base_api_url = f"https://api.github.com/repos/{owner}/{repo}"

    # Function to make API requests with enhanced rate limit handling
    def make_github_request(url, headers):
        max_retries = 3
        retry_count = 0
        backoff_time = 2  # Start with 2 seconds backoff, will increase exponentially

        while retry_count < max_retries:
            try:
                response = requests.get(url, headers=headers, timeout=30)

                if response.status_code == 200:
                    return response.json()
                elif (
                    response.status_code == 403
                    and "rate limit exceeded" in response.text.lower()
                ):
                    retry_count += 1

                    # Get rate limit information
                    try:
                        rate_info = requests.get(
                            "https://api.github.com/rate_limit", headers=headers, timeout=10
                        ).json()
                        
                        # Extract and display remaining requests
                        remaining = rate_info.get("resources", {}).get("core", {}).get("remaining", 0)
                        limit = rate_info.get("resources", {}).get("core", {}).get("limit", 0)
                        reset_time = rate_info.get("resources", {}).get("core", {}).get("reset", 0)
                        current_time = time.time()
                        
                        # Calculate wait time with some buffer
                        wait_time = max(reset_time - current_time + 10, 10)
                        
                        # Format reset time as human readable
                        reset_time_formatted = time.strftime(
                            "%Y-%m-%d %H:%M:%S", time.localtime(reset_time)
                        )
                        
                        print(
                            f"GitHub API rate limit status: {remaining}/{limit} requests remaining. "
                            f"Reset at {reset_time_formatted} (in ~{wait_time:.1f} seconds)"
                        )
                    except Exception as e:
                        # If we can't get rate limit info, use exponential backoff
                        wait_time = backoff_time
                        backoff_time *= 2  # Exponential backoff
                        print(f"Couldn't get rate limit info: {str(e)}. Using backoff of {wait_time}s")

                    if retry_count < max_retries:
                        print(
                            f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries}"
                        )
                        # Cap wait time at 5 minutes to avoid excessive waiting
                        time.sleep(min(wait_time, 300))
                    else:
                        token_hint = "" if "Authorization" in headers else " Consider using a GitHub token to increase your rate limits."
                        raise Exception(
                            f"GitHub API rate limit exceeded. Please try again later.{token_hint}"
                            f"\nReset time: {reset_time_formatted if 'reset_time_formatted' in locals() else 'unknown'}"
                        )
                elif response.status_code == 404:
                    raise Exception(f"Resource not found at {url}. Please check the repository URL.")
                else:
                    # Try to extract error message from GitHub API response
                    try:
                        error_msg = response.json().get("message", "")
                        if error_msg:
                            raise Exception(f"GitHub API error: {error_msg} (Status code: {response.status_code})")
                    except:
                        pass
                    
                    # Fall back to standard error raising
                    response.raise_for_status()
            
            except requests.exceptions.RequestException as e:
                retry_count += 1
                if retry_count >= max_retries:
                    raise Exception(f"Network error connecting to GitHub API: {str(e)}")
                
                # Use exponential backoff for connection errors
                print(f"Request error: {str(e)}. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff

        raise Exception(
            f"Failed to make GitHub API request after {max_retries} retries"
        )

    # Get the repository contents
    try:
        contents = make_github_request(f"{base_api_url}/contents", headers)
    except Exception as e:
        raise Exception(f"Error fetching repository contents: {str(e)}")

    # Structure to store file contents
    file_contents = {}

    # Track number of files analyzed
    files_analyzed = 0

    # Initialize file metadata
    file_metadata = {}

    # Extract folder structure recursively with file content extraction
    folder_structure, file_metadata = get_folder_structure_with_contents(
        contents,
        base_api_url,
        headers,
        max_depth=4,
        file_contents=file_contents,
        max_file_size=max_file_size,
        file_limit=file_limit,
        files_analyzed=files_analyzed,
        file_metadata=file_metadata,
    )

    # Identify frameworks used in the repository
    frameworks = identify_frameworks(folder_structure, file_contents)

    # Get additional information about the repository
    repo_info = make_github_request(base_api_url, headers)

    # Package the analysis results
    analysis_result = {
        "folder_structure": folder_structure,
        "frameworks": frameworks,
        "file_contents": file_contents,
        "file_metadata": file_metadata,
        "additional_info": {
            "description": repo_info.get("description", ""),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "language": repo_info.get("language", ""),
            "last_update": repo_info.get("updated_at", ""),
            "open_issues": repo_info.get("open_issues_count", 0),
        },
    }

    # Cache the results in memory
    repo_cache[repo_url] = analysis_result
    
    # Also cache the results persistently
    try:
        # Cache the main analysis result
        cache_repository_data(repo_url, analysis_result)
        
        # Cache individual file contents
        for file_path, content in file_contents.items():
            cache_file_content(file_path, content)
    except Exception as e:
        print(f"Warning: Failed to persist cache: {str(e)}")

    return analysis_result


def get_folder_structure_with_contents(
    contents,
    base_api_url,
    headers,
    path="",
    max_depth=4,
    current_depth=0,
    file_contents={},
    max_file_size=500000,
    file_limit=100,
    files_analyzed=0,
    file_metadata={},
):
    """
    Recursively extract the folder structure and file contents of a repository

    Args:
        contents (list): List of file/directory contents from GitHub API
        base_api_url (str): Base API URL for the repository
        headers (dict): Headers for API requests
        path (str): Current path within the repository
        max_depth (int): Maximum recursion depth
        current_depth (int): Current recursion depth
        file_contents (dict): Dictionary to store file contents
        max_file_size (int): Maximum file size to read (bytes)
        file_limit (int): Maximum number of files to analyze deeply
        files_analyzed (int): Current count of files analyzed
        file_metadata (dict): Dictionary to store file metadata

    Returns:
        tuple: (Formatted folder structure, file metadata dictionary)
    """
    if current_depth > max_depth:
        return f"{path} (max depth reached)\n", file_metadata

    result = ""

    # Sort contents to put directories first, then files
    sorted_contents = sorted(contents, key=lambda x: 0 if x["type"] == "dir" else 1)

    for item in sorted_contents:
        item_path = f"{path}{'/' if path else ''}{item['name']}"

        if item["type"] == "file":
            result += f"📄 {item_path}\n"

            # Skip files if we've reached the limit
            if files_analyzed >= file_limit:
                file_metadata[item_path] = {
                    "size": item.get("size", 0),
                    "type": (
                        os.path.splitext(item["name"])[1][1:]
                        if os.path.splitext(item["name"])[1]
                        else "unknown"
                    ),
                    "url": item.get("html_url", ""),
                    "skipped": True,
                    "reason": "File limit reached",
                }
                continue

            # Determine if file should be analyzed based on extension
            file_ext = os.path.splitext(item["name"])[1].lower()
            analyzable_extensions = [
                ".py",
                ".js",
                ".jsx",
                ".ts",
                ".tsx",
                ".java",
                ".c",
                ".cpp",
                ".cs",
                ".go",
                ".rb",
                ".php",
                ".html",
                ".css",
                ".json",
                ".yml",
                ".yaml",
                ".md",
                ".txt",
                ".sh",
                ".bat",
                ".ps1",
                ".sql",
                ".rs",
                ".swift",
                ".kt",
                ".kts",
                ".dart",
                ".lua",
                ".r",
                ".pl",
                ".pm",
            ]

            # Skip binary files and other non-code files
            skip_extensions = [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".svg",
                ".ico",
                ".webp",
                ".mp3",
                ".mp4",
                ".wav",
                ".avi",
                ".mov",
                ".pdf",
                ".zip",
                ".tar",
                ".gz",
                ".rar",
                ".exe",
                ".dll",
                ".so",
                ".dylib",
                ".class",
                ".jar",
                ".war",
                ".ear",
                ".pyc",
                ".pyo",
                ".o",
                ".obj",
            ]

            # Skip large files or binary files
            if (
                item.get("size", 0) > max_file_size
                or file_ext in skip_extensions
                or "node_modules" in item_path
                or "__pycache__" in item_path
            ):
                # Record metadata but don't fetch content
                file_metadata[item_path] = {
                    "size": item.get("size", 0),
                    "type": file_ext[1:] if file_ext else "unknown",
                    "url": item.get("html_url", ""),
                    "skipped": True,
                    "reason": "Size limit exceeded or binary file",
                }
                continue

            # Try to get file content if it's a code file
            if file_ext in analyzable_extensions or (
                file_ext == "" and item.get("size", 0) < max_file_size
            ):
                try:
                    # Check in-memory cache first
                    if item_path in file_content_cache:
                        file_contents[item_path] = file_content_cache[item_path]

                        # Record metadata
                        file_metadata[item_path] = {
                            "size": item.get("size", 0),
                            "type": file_ext[1:] if file_ext else "text",
                            "url": item.get("html_url", ""),
                            "skipped": False,
                            "cached": True,
                            "cache_source": "memory",
                        }

                        files_analyzed += 1
                    # Check persistent cache
                    elif "get_cached_file_content" in globals() or hasattr(sys.modules.get('app.utils', None), 'get_cached_file_content'):
                        # Import function if not already available
                        if "get_cached_file_content" not in globals():
                            from app.utils import get_cached_file_content
                            
                        cached_content = get_cached_file_content(item_path)
                        if cached_content:
                            file_contents[item_path] = cached_content
                            file_content_cache[item_path] = cached_content
                            
                            # Record metadata
                            file_metadata[item_path] = {
                                "size": item.get("size", 0),
                                "type": file_ext[1:] if file_ext else "text",
                                "url": item.get("html_url", ""),
                                "skipped": False,
                                "cached": True,
                                "cache_source": "disk",
                            }
                            
                            files_analyzed += 1
                    else:
                        # Fetch file content
                        file_response = requests.get(item["url"], headers=headers)

                        if file_response.status_code == 200:
                            file_data = file_response.json()

                            # GitHub API returns base64 encoded content
                            if (
                                "content" in file_data
                                and file_data.get("encoding") == "base64"
                            ):
                                try:
                                    content = base64.b64decode(
                                        file_data["content"]
                                    ).decode("utf-8", errors="replace")
                                    file_contents[item_path] = content
                                    file_content_cache[item_path] = content

                                    # Record metadata
                                    file_metadata[item_path] = {
                                        "size": item.get("size", 0),
                                        "type": file_ext[1:] if file_ext else "text",
                                        "url": item.get("html_url", ""),
                                        "last_modified": file_data.get(
                                            "last_modified", ""
                                        ),
                                        "skipped": False,
                                    }

                                    files_analyzed += 1
                                except UnicodeDecodeError:
                                    # Try to detect encoding
                                    try:
                                        raw_content = base64.b64decode(
                                            file_data["content"]
                                        )
                                        detected = chardet.detect(raw_content)
                                        if detected["confidence"] > 0.7:
                                            content = raw_content.decode(
                                                detected["encoding"], errors="replace"
                                            )
                                            file_contents[item_path] = content
                                            file_content_cache[item_path] = content

                                            # Record metadata
                                            file_metadata[item_path] = {
                                                "size": item.get("size", 0),
                                                "type": (
                                                    file_ext[1:] if file_ext else "text"
                                                ),
                                                "url": item.get("html_url", ""),
                                                "last_modified": file_data.get(
                                                    "last_modified", ""
                                                ),
                                                "encoding": detected["encoding"],
                                                "skipped": False,
                                            }

                                            files_analyzed += 1
                                        else:
                                            # Record that we couldn't decode the file
                                            file_metadata[item_path] = {
                                                "size": item.get("size", 0),
                                                "type": (
                                                    file_ext[1:]
                                                    if file_ext
                                                    else "unknown"
                                                ),
                                                "url": item.get("html_url", ""),
                                                "skipped": True,
                                                "reason": "Unable to detect encoding",
                                            }
                                    except:
                                        # Record that we couldn't decode the file
                                        file_metadata[item_path] = {
                                            "size": item.get("size", 0),
                                            "type": (
                                                file_ext[1:] if file_ext else "unknown"
                                            ),
                                            "url": item.get("html_url", ""),
                                            "skipped": True,
                                            "reason": "Unable to decode content",
                                        }
                except Exception as e:
                    print(f"Error fetching content for {item_path}: {str(e)}")
                    # Record error in metadata
                    file_metadata[item_path] = {
                        "size": item.get("size", 0),
                        "type": file_ext[1:] if file_ext else "unknown",
                        "url": item.get("html_url", ""),
                        "skipped": True,
                        "reason": f"Error: {str(e)}",
                    }
            else:
                # Record metadata for non-analyzed files
                file_metadata[item_path] = {
                    "size": item.get("size", 0),
                    "type": file_ext[1:] if file_ext else "unknown",
                    "url": item.get("html_url", ""),
                    "skipped": True,
                    "reason": "Not a recognized code file",
                }

        elif item["type"] == "dir":
            result += f"📁 {item_path}/\n"

            # Don't recursively fetch certain directories that are often large or not meaningful for analysis
            skip_dirs = [
                "node_modules",
                ".git",
                "build",
                "dist",
                "target",
                "venv",
                "env",
                ".env",
                "__pycache__",
                ".pytest_cache",
                "vendor",
                "bower_components",
            ]

            if item["name"] not in skip_dirs and current_depth < max_depth:
                try:
                    # Make API request to get directory contents
                    dir_contents = requests.get(item["url"], headers=headers).json()

                    # If API returned a list, it's a valid directory
                    if isinstance(dir_contents, list):
                        # Add indentation for subdirectories
                        sub_structure, file_metadata = (
                            get_folder_structure_with_contents(
                                dir_contents,
                                base_api_url,
                                headers,
                                item_path,
                                max_depth,
                                current_depth + 1,
                                file_contents,
                                max_file_size,
                                file_limit,
                                files_analyzed,
                                file_metadata,
                            )
                        )

                        # Indent the sub-structure
                        for line in sub_structure.splitlines():
                            if line.strip():
                                result += f"    {line}\n"
                except Exception as e:
                    result += f"    Error accessing {item_path}: {str(e)}\n"

    return result, file_metadata


def identify_frameworks(folder_structure: str, file_contents: dict = None) -> list:
    """
    Identify frameworks and technologies used in the repository based on folder structure and file contents

    Args:
        folder_structure (str): Formatted folder structure
        file_contents (dict, optional): Dictionary of file contents for deeper analysis

    Returns:
        list: List of identified frameworks and technologies
    """
    frameworks = []

    # Define patterns to look for in folder structure
    framework_patterns = {
        "React": [r"react", r"jsx", r"tsx", r"next.js", r"next.config.js"],
        "Angular": [r"angular", r"ng-", r"angular.json"],
        "Vue.js": [r"vue", r"nuxt", r"vuex"],
        "Node.js": [r"node_modules", r"package.json", r"npm", r"yarn"],
        "Django": [r"django", r"wsgi.py", r"asgi.py", r"manage.py"],
        "Flask": [r"flask", r"app.py", r"wsgi.py"],
        "Ruby on Rails": [r"rails", r"gemfile", r"ruby"],
        "Spring": [r"spring", r"application.properties", r"application.yml"],
        "Laravel": [r"laravel", r"artisan", r"blade.php"],
        "Express": [r"express", r"app.js", r"routes"],
        "TensorFlow": [r"tensorflow", r"tf.", r".pb"],
        "PyTorch": [r"torch", r"pytorch"],
        "Docker": [r"dockerfile", r"docker-compose"],
        "Kubernetes": [r"k8s", r"kubernetes", r"helm"],
        "GraphQL": [r"graphql", r"gql", r"apollo"],
        "REST API": [r"api", r"rest", r"swagger", r"openapi"],
        "jQuery": [r"jquery"],
        "Bootstrap": [r"bootstrap"],
        "Tailwind CSS": [r"tailwind"],
        "Redux": [r"redux", r"store.js", r"actions", r"reducers"],
        "MongoDB": [r"mongo", r"mongoose"],
        "PostgreSQL": [r"postgres", r"pg"],
        "MySQL": [r"mysql", r"sequelize"],
        "Redis": [r"redis"],
        "Elasticsearch": [r"elastic", r"elasticsearch"],
        ".NET": [r"\.csproj", r"\.cs", r"aspnet"],
        "C#": [r"\.cs"],
        "Java": [r"\.java", r"maven", r"gradle"],
        "Python": [r"\.py", r"requirements.txt", r"setup.py"],
        "JavaScript": [r"\.js"],
        "TypeScript": [r"\.ts"],
        "Go": [r"\.go", r"go.mod"],
        "Rust": [r"\.rs", r"cargo.toml"],
        "PHP": [r"\.php", r"composer.json"],
        "Swift": [r"\.swift"],
        "Kotlin": [r"\.kt"],
        "R": [r"\.r", r"\.rmd", r"\.rproj"],
        "MATLAB": [r"\.m"],
        "C++": [r"\.cpp", r"\.cxx", r"\.cc"],
        "C": [r"\.c", r"\.h"],
        "Scala": [r"\.scala", r"\.sbt"],
        "Clojure": [r"\.clj"],
        "Haskell": [r"\.hs"],
        "Elixir": [r"\.ex", r"\.exs"],
        "Erlang": [r"\.erl"],
        "Solidity": [r"\.sol"],
        "WebAssembly": [r"\.wasm", r"wasm"],
    }

    # Check each pattern against the folder structure
    for framework, patterns in framework_patterns.items():
        for pattern in patterns:
            if re.search(pattern, folder_structure, re.IGNORECASE):
                if framework not in frameworks:
                    frameworks.append(framework)
                break

    # If file contents are provided, perform deeper analysis
    if file_contents:
        # Define patterns to look for in file contents
        content_patterns = {
            "React": [
                r"import\s+React",
                r"from\s+['\"]react['\"]",
                r"React\.Component",
                r"useState",
                r"useEffect",
            ],
            "Angular": [
                r"@angular\/core",
                r"NgModule",
                r"Component\(",
                r"Injectable\(",
            ],
            "Vue.js": [
                r"import\s+Vue",
                r"from\s+['\"]vue['\"]",
                r"new\s+Vue\(",
                r"createApp",
            ],
            "jQuery": [r"\$\(\s*['\"]", r"jQuery\("],
            "Redux": [r"createStore", r"useReducer", r"useSelector", r"useDispatch"],
            "Express": [
                r"const\s+express\s*=\s*require\(['\"]express['\"]\)",
                r"import\s+express",
                r"app\.get\(",
                r"app\.use\(",
                r"app\.post\(",
            ],
            "GraphQL": [r"import\s+{\s*GraphQL", r"gql`", r"Apollo", r"useQuery"],
            "MongoDB": [r"mongoose", r"MongoClient", r"mongodb:\/\/"],
            "PostgreSQL": [r"const\s+pg\s*=", r"Pool\(", r"psql"],
            "Django": [r"from\s+django", r"urlpatterns", r"DJANGO_SETTINGS"],
            "Flask": [r"from\s+flask", r"Flask\(__name__\)"],
            "Bootstrap": [
                r"class\s*=\s*['\"]btn",
                r"class\s*=\s*['\"]container",
                r"class\s*=\s*['\"]row",
            ],
            "Tailwind CSS": [r"class\s*=\s*['\"](?:[a-z0-9:-]+\s+)+[a-z0-9:-]+['\"]"],
        }

        # Check each file for framework patterns
        for file_path, content in file_contents.items():
            file_ext = os.path.splitext(file_path)[1].lower()

            # Check patterns based on file content
            for framework, patterns in content_patterns.items():
                # Skip if already detected
                if framework in frameworks:
                    continue

                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        frameworks.append(framework)
                        break

            # Check for package.json to identify Node.js dependencies
            if file_path.endswith("package.json"):
                try:
                    import json

                    package_data = json.loads(content)

                    # Check dependencies and devDependencies
                    all_deps = {}
                    if "dependencies" in package_data:
                        all_deps.update(package_data["dependencies"])
                    if "devDependencies" in package_data:
                        all_deps.update(package_data["devDependencies"])

                    # Map dependencies to frameworks
                    dep_to_framework = {
                        "react": "React",
                        "react-dom": "React",
                        "next": "Next.js",
                        "@angular/core": "Angular",
                        "vue": "Vue.js",
                        "nuxt": "Nuxt.js",
                        "express": "Express",
                        "koa": "Koa",
                        "fastify": "Fastify",
                        "gatsby": "Gatsby",
                        "mongoose": "MongoDB",
                        "sequelize": "SQL ORM",
                        "tailwindcss": "Tailwind CSS",
                        "bootstrap": "Bootstrap",
                        "redux": "Redux",
                        "mobx": "MobX",
                        "apollo-client": "Apollo GraphQL",
                        "graphql": "GraphQL",
                        "jest": "Jest Testing",
                        "mocha": "Mocha Testing",
                        "chai": "Chai Testing",
                        "cypress": "Cypress Testing",
                        "webpack": "Webpack",
                        "rollup": "Rollup",
                        "parcel": "Parcel",
                        "typescript": "TypeScript",
                        "lodash": "Lodash",
                        "axios": "Axios",
                        "firebase": "Firebase",
                        "aws-sdk": "AWS SDK",
                        "electron": "Electron",
                    }

                    # Add frameworks based on dependencies
                    for dep in all_deps:
                        if (
                            dep in dep_to_framework
                            and dep_to_framework[dep] not in frameworks
                        ):
                            frameworks.append(dep_to_framework[dep])
                except:
                    pass

            # Check for requirements.txt to identify Python dependencies
            elif file_path.endswith("requirements.txt"):
                try:
                    lines = content.split("\n")
                    # Map Python packages to frameworks
                    pkg_to_framework = {
                        "django": "Django",
                        "flask": "Flask",
                        "fastapi": "FastAPI",
                        "tornado": "Tornado",
                        "pyramid": "Pyramid",
                        "sqlalchemy": "SQLAlchemy",
                        "pandas": "Pandas",
                        "numpy": "NumPy",
                        "tensorflow": "TensorFlow",
                        "torch": "PyTorch",
                        "sklearn": "Scikit-learn",
                        "pytest": "Pytest",
                        "celery": "Celery",
                        "requests": "Requests",
                        "beautifulsoup4": "BeautifulSoup",
                        "scrapy": "Scrapy",
                        "matplotlib": "Matplotlib",
                        "seaborn": "Seaborn",
                        "dash": "Dash",
                        "streamlit": "Streamlit",
                    }

                    for line in lines:
                        # Extract package name (ignoring version)
                        pkg = (
                            line.strip()
                            .split("==")[0]
                            .split(">=")[0]
                            .split("<=")[0]
                            .lower()
                        )
                        if (
                            pkg in pkg_to_framework
                            and pkg_to_framework[pkg] not in frameworks
                        ):
                            frameworks.append(pkg_to_framework[pkg])
                except:
                    pass

    return frameworks


def analyze_code_quality(file_contents: dict) -> dict:
    """
    Analyze code quality metrics from file contents

    Args:
        file_contents (dict): Dictionary of file paths and their contents

    Returns:
        dict: Code quality metrics
    """
    metrics = {
        "total_files": len(file_contents),
        "total_lines": 0,
        "code_lines": 0,
        "comment_lines": 0,
        "blank_lines": 0,
        "large_files": [],
        "complex_functions": [],
        "potential_issues": [],
    }

    for file_path, content in file_contents.items():
        file_ext = os.path.splitext(file_path)[1].lower()

        # Count lines
        lines = content.split("\n")
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())

        metrics["total_lines"] += total_lines
        metrics["blank_lines"] += blank_lines

        # Count comment lines based on file type
        comment_lines = 0
        if file_ext in [".py"]:
            comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        elif file_ext in [".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".cs"]:
            comment_lines = sum(1 for line in lines if line.strip().startswith("//"))

        metrics["comment_lines"] += comment_lines
        metrics["code_lines"] += total_lines - blank_lines - comment_lines

        # Track large files (over 500 lines)
        if total_lines > 500:
            metrics["large_files"].append({"path": file_path, "lines": total_lines})

        # Identify long functions/methods
        if file_ext in [".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".php"]:
            # Python function detection
            if file_ext == ".py":
                in_function = False
                function_name = ""
                function_lines = 0
                function_start_line = 0

                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Function start detection
                    if (
                        stripped.startswith("def ") or stripped.startswith("async def ")
                    ) and stripped.endswith(":"):
                        if (
                            in_function and function_lines > 50
                        ):  # Threshold for "complex" function
                            metrics["complex_functions"].append(
                                {
                                    "file": file_path,
                                    "function": function_name,
                                    "lines": function_lines,
                                    "line_number": function_start_line + 1,
                                }
                            )

                        # Extract function name
                        if "async def " in stripped:
                            function_name = (
                                stripped.split("async def ")[1].split("(")[0].strip()
                            )
                        else:
                            function_name = (
                                stripped.split("def ")[1].split("(")[0].strip()
                            )

                        function_start_line = i
                        function_lines = 1
                        in_function = True
                    elif in_function:
                        # Check indentation to see if still in function
                        if (
                            (not stripped or stripped.startswith("#"))
                            or line.startswith(" ")
                            or line.startswith("\t")
                        ):
                            function_lines += 1
                        else:
                            # Function ended
                            if function_lines > 50:  # Threshold for "complex" function
                                metrics["complex_functions"].append(
                                    {
                                        "file": file_path,
                                        "function": function_name,
                                        "lines": function_lines,
                                        "line_number": function_start_line + 1,
                                    }
                                )
                            in_function = False

                # Check if the last function in the file is complex
                if in_function and function_lines > 50:
                    metrics["complex_functions"].append(
                        {
                            "file": file_path,
                            "function": function_name,
                            "lines": function_lines,
                            "line_number": function_start_line + 1,
                        }
                    )

            # JavaScript/TypeScript function detection
            elif file_ext in [".js", ".jsx", ".ts", ".tsx"]:
                in_function = False
                function_name = ""
                function_lines = 0
                function_start_line = 0
                brace_count = 0

                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Function declaration patterns
                    if not in_function:
                        # Function declaration
                        if re.match(
                            r"^(async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(", stripped
                        ):
                            function_name = re.match(
                                r"^(async\s+)?function\s+([a-zA-Z0-9_$]+)", stripped
                            ).group(2)
                            function_start_line = i
                            function_lines = 1
                            in_function = True
                            brace_count = stripped.count("{") - stripped.count("}")

                        # Arrow function
                        elif re.match(
                            r"^(const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(\(.*?\)|[a-zA-Z0-9_$]+)\s*=>",
                            stripped,
                        ):
                            function_name = re.match(
                                r"^(const|let|var)\s+([a-zA-Z0-9_$]+)", stripped
                            ).group(2)
                            function_start_line = i
                            function_lines = 1
                            in_function = True
                            brace_count = stripped.count("{") - stripped.count("}")

                        # Class method
                        elif re.match(
                            r"^\s*(async\s+)?([a-zA-Z0-9_$]+)\s*\(", stripped
                        ) and not stripped.startswith(("if", "for", "while", "switch")):
                            function_name = re.match(
                                r"^\s*(async\s+)?([a-zA-Z0-9_$]+)", stripped
                            ).group(2)
                            function_start_line = i
                            function_lines = 1
                            in_function = True
                            brace_count = stripped.count("{") - stripped.count("}")
                    else:
                        # Count lines and track braces
                        function_lines += 1
                        brace_count += stripped.count("{") - stripped.count("}")

                        # Function end detection
                        if brace_count <= 0 and ("}" in stripped or ";" in stripped):
                            if (
                                function_lines > 40
                            ):  # Threshold for "complex" JS function
                                metrics["complex_functions"].append(
                                    {
                                        "file": file_path,
                                        "function": function_name,
                                        "lines": function_lines,
                                        "line_number": function_start_line + 1,
                                    }
                                )
                            in_function = False

                # Check if the last function in the file is complex
                if in_function and function_lines > 40:
                    metrics["complex_functions"].append(
                        {
                            "file": file_path,
                            "function": function_name,
                            "lines": function_lines,
                            "line_number": function_start_line + 1,
                        }
                    )

            # Java function detection
            elif file_ext in [".java"]:
                in_method = False
                method_name = ""
                method_lines = 0
                method_start_line = 0
                brace_count = 0

                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # Method declaration pattern
                    if not in_method:
                        # Method with modifiers, return type, name and parameters
                        method_match = re.match(
                            r"^(?:public|private|protected|static|final|abstract|synchronized|\s)*\s+[a-zA-Z0-9_<>[\],\s.]+\s+([a-zA-Z0-9_]+)\s*\(",
                            stripped,
                        )
                        if method_match and "{" in stripped:
                            method_name = method_match.group(1)
                            method_start_line = i
                            method_lines = 1
                            in_method = True
                            brace_count = stripped.count("{") - stripped.count("}")
                    else:
                        # Count lines and track braces
                        method_lines += 1
                        brace_count += stripped.count("{") - stripped.count("}")

                        # Method end detection
                        if brace_count <= 0 and "}" in stripped:
                            if method_lines > 60:  # Threshold for "complex" Java method
                                metrics["complex_functions"].append(
                                    {
                                        "file": file_path,
                                        "function": method_name,
                                        "lines": method_lines,
                                        "line_number": method_start_line + 1,
                                    }
                                )
                            in_method = False

                # Check if the last method in the file is complex
                if in_method and method_lines > 60:
                    metrics["complex_functions"].append(
                        {
                            "file": file_path,
                            "function": method_name,
                            "lines": method_lines,
                            "line_number": method_start_line + 1,
                        }
                    )

        # Detect potential security issues
        if file_ext in [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]:
            for i, line in enumerate(lines):
                stripped = line.strip()

                # Skip comment lines
                if file_ext == ".py" and stripped.startswith("#"):
                    continue
                if file_ext in [".js", ".jsx", ".ts", ".tsx", ".java"] and (
                    stripped.startswith("//") or stripped.startswith("/*")
                ):
                    continue

                # Check for hardcoded secrets/credentials
                if re.search(
                    r'(api[_-]?key|apikey|secret|password|token|credential|auth)[_-]?[^a-z]*\s*=\s*[\'"]\S+[\'"]',
                    stripped,
                    re.IGNORECASE,
                ):
                    if not re.search(
                        r"(process\.env|os\.environ|\.env)", stripped, re.IGNORECASE
                    ):  # Skip environment variables
                        metrics["potential_issues"].append(
                            {
                                "file": file_path,
                                "line": i + 1,
                                "issue": "Possible hardcoded credential/secret",
                                "snippet": stripped,
                            }
                        )

                # Check for SQL injection vulnerabilities
                if re.search(
                    r"(execute|query|select|insert|update|delete).*\+\s*",
                    stripped,
                    re.IGNORECASE,
                ) and re.search(
                    r"(req\.|request\.|params|body|query|user|input)",
                    stripped,
                    re.IGNORECASE,
                ):
                    metrics["potential_issues"].append(
                        {
                            "file": file_path,
                            "line": i + 1,
                            "issue": "Potential SQL injection vulnerability",
                            "snippet": stripped,
                        }
                    )

                # Check for XSS vulnerabilities in JavaScript/TypeScript
                if (
                    file_ext in [".js", ".jsx", ".ts", ".tsx"]
                    and re.search(
                        r"(innerHTML|outerHTML|document\.write|eval)\s*=",
                        stripped,
                        re.IGNORECASE,
                    )
                    and re.search(
                        r"(req\.|request\.|params|body|query|user|input)",
                        stripped,
                        re.IGNORECASE,
                    )
                ):
                    metrics["potential_issues"].append(
                        {
                            "file": file_path,
                            "line": i + 1,
                            "issue": "Potential XSS vulnerability",
                            "snippet": stripped,
                        }
                    )

    return metrics
