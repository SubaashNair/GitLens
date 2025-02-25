# app/analyzer.py
import re
import requests
import time
import os
from urllib.parse import urlparse

# Simple caching mechanism to reduce API calls
repo_cache = {}


def analyze_repo(repo_url, github_token=None):
    """
    Analyze a GitHub repository and extract folder structure, frameworks used, etc.

    Args:
        repo_url (str): URL of the GitHub repository to analyze
        github_token (str, optional): GitHub personal access token for authentication

    Returns:
        dict: Analysis results including folder structure and frameworks
    """
    # Check if this repo is in the cache
    if repo_url in repo_cache:
        print(f"Using cached analysis for {repo_url}")
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

    # Function to make API requests with rate limit handling
    def make_github_request(url, headers):
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                return response.json()
            elif (
                response.status_code == 403
                and "rate limit exceeded" in response.text.lower()
            ):
                retry_count += 1

                # Get rate limit information
                rate_info = requests.get(
                    "https://api.github.com/rate_limit", headers=headers
                ).json()
                reset_time = (
                    rate_info.get("resources", {}).get("core", {}).get("reset", 0)
                )
                current_time = time.time()

                # Calculate wait time with some buffer
                wait_time = max(reset_time - current_time + 10, 10)

                if retry_count < max_retries:
                    print(
                        f"Rate limit exceeded. Waiting {wait_time:.2f} seconds before retry {retry_count}/{max_retries}"
                    )
                    time.sleep(min(wait_time, 60))  # Wait at most a minute
                else:
                    raise Exception(
                        f"GitHub API rate limit exceeded. Please try again later or use a GitHub token. Reset time: {reset_time}"
                    )
            else:
                response.raise_for_status()

        raise Exception(
            f"Failed to make GitHub API request after {max_retries} retries"
        )

    # Get the repository contents
    try:
        contents = make_github_request(f"{base_api_url}/contents", headers)
    except Exception as e:
        raise Exception(f"Error fetching repository contents: {str(e)}")

    # Extract folder structure recursively with a maximum depth to avoid excessive API calls
    folder_structure = get_folder_structure(
        contents, base_api_url, headers, max_depth=4
    )

    # Identify frameworks used in the repository
    frameworks = identify_frameworks(folder_structure)

    # Get additional information about the repository
    repo_info = make_github_request(base_api_url, headers)

    # Package the analysis results
    analysis_result = {
        "folder_structure": folder_structure,
        "frameworks": frameworks,
        "additional_info": {
            "description": repo_info.get("description", ""),
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "language": repo_info.get("language", ""),
            "last_update": repo_info.get("updated_at", ""),
            "open_issues": repo_info.get("open_issues_count", 0),
        },
    }

    # Cache the results
    repo_cache[repo_url] = analysis_result

    return analysis_result


def get_folder_structure(
    contents, base_api_url, headers, path="", max_depth=4, current_depth=0
):
    """
    Recursively extract the folder structure of a repository

    Args:
        contents (list): List of file/directory contents from GitHub API
        base_api_url (str): Base API URL for the repository
        headers (dict): Headers for API requests
        path (str): Current path within the repository
        max_depth (int): Maximum recursion depth
        current_depth (int): Current recursion depth

    Returns:
        str: Formatted folder structure
    """
    if current_depth > max_depth:
        return f"{path} (max depth reached)\n"

    result = ""

    for item in contents:
        item_path = f"{path}{'/' if path else ''}{item['name']}"

        if item["type"] == "file":
            result += f"📄 {item_path}\n"
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
            ]

            if item["name"] not in skip_dirs and current_depth < max_depth:
                try:
                    # Make API request to get directory contents
                    dir_contents = requests.get(item["url"], headers=headers).json()

                    # If API returned a list, it's a valid directory
                    if isinstance(dir_contents, list):
                        # Add indentation for subdirectories
                        sub_structure = get_folder_structure(
                            dir_contents,
                            base_api_url,
                            headers,
                            item_path,
                            max_depth,
                            current_depth + 1,
                        )

                        # Indent the sub-structure
                        for line in sub_structure.splitlines():
                            if line.strip():
                                result += f"    {line}\n"
                except Exception as e:
                    result += f"    Error accessing {item_path}: {str(e)}\n"

    return result


def identify_frameworks(folder_structure):
    """
    Identify frameworks and technologies used in the repository based on folder structure

    Args:
        folder_structure (str): Formatted folder structure

    Returns:
        list: List of identified frameworks and technologies
    """
    frameworks = []

    # Define patterns to look for
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

    return frameworks
