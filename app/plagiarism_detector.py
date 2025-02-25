# app/plagiarism_detector.py
import os
import re
import requests
import hashlib
import time
from difflib import SequenceMatcher
import io
import random


class PlagiarismDetector:
    def __init__(self, github_token=None):
        """
        Initialize the plagiarism detector

        Args:
            github_token (str, optional): GitHub personal access token for authentication
        """
        self.github_token = github_token
        self.headers = {"Accept": "application/vnd.github.v3+json"}

        if github_token:
            self.headers["Authorization"] = f"token {github_token}"

    def detect_plagiarism(self, repo_url, max_files=10):
        """
        Detect potential plagiarism in a GitHub repository

        Args:
            repo_url (str): URL of the GitHub repository to check
            max_files (int): Maximum number of files to check (to avoid rate limits)

        Returns:
            dict: Results of plagiarism detection with potentially plagiarized files and their sources
        """
        # Parse the GitHub URL to extract owner and repo name
        parts = repo_url.strip("/").split("/")
        if len(parts) < 5 or parts[2] != "github.com":
            raise ValueError(
                "Invalid GitHub repository URL. Expected format: https://github.com/owner/repo"
            )

        owner = parts[3]
        repo = parts[4]

        base_api_url = f"https://api.github.com/repos/{owner}/{repo}"

        # Get list of code files to check
        code_files = self._get_code_files(base_api_url, max_files)

        results = {
            "plagiarism_detected": False,
            "checked_files_count": len(code_files),
            "suspicious_files": [],
            "summary": "",
        }

        if not code_files:
            results["summary"] = "No code files found to check for plagiarism."
            return results

        # Check each file for potential plagiarism
        for file_info in code_files:
            file_path = file_info["path"]
            file_content = self._get_file_content(file_info["download_url"])

            if not file_content:
                continue

            # Check this file for plagiarism using different methods
            plagiarism_check = self._check_file_plagiarism(file_path, file_content)

            if plagiarism_check["is_suspicious"]:
                results["plagiarism_detected"] = True
                results["suspicious_files"].append(
                    {
                        "file": file_path,
                        "confidence": plagiarism_check["confidence"],
                        "potential_source": plagiarism_check["potential_source"],
                        "match_type": plagiarism_check["match_type"],
                        "snippet": plagiarism_check["snippet"],
                    }
                )

        # Generate summary
        if results["plagiarism_detected"]:
            results["summary"] = (
                f"Potential plagiarism detected in {len(results['suspicious_files'])} out of {len(code_files)} checked files."
            )
        else:
            results["summary"] = (
                f"No obvious plagiarism detected in the {len(code_files)} files checked."
            )

        return results

    def _get_code_files(self, base_api_url, max_files):
        """
        Get a list of code files from the repository

        Args:
            base_api_url (str): Base API URL for the repository
            max_files (int): Maximum number of files to return

        Returns:
            list: List of code file information
        """
        code_files = []
        extensions = [
            ".py",
            ".js",
            ".java",
            ".cpp",
            ".c",
            ".cs",
            ".php",
            ".rb",
            ".go",
            ".swift",
            ".ts",
            ".html",
            ".css",
        ]

        try:
            # Get repository contents
            response = requests.get(
                f"{base_api_url}/git/trees/main?recursive=1", headers=self.headers
            )

            # If main branch doesn't exist, try master
            if response.status_code != 200:
                response = requests.get(
                    f"{base_api_url}/git/trees/master?recursive=1", headers=self.headers
                )

            if response.status_code != 200:
                print(f"Error getting repository file tree: {response.status_code}")
                return code_files

            tree = response.json().get("tree", [])

            # Filter for code files with specific extensions
            for item in tree:
                if item["type"] == "blob":  # It's a file
                    file_path = item["path"]
                    file_ext = os.path.splitext(file_path)[1].lower()

                    # Check if it's a code file
                    if file_ext in extensions:
                        # Skip large files, minified files, and node_modules
                        if (
                            item.get("size", 0) < 100000
                            and "min." not in file_path.lower()
                            and "node_modules" not in file_path
                            and "vendor" not in file_path
                            and "dist" not in file_path
                        ):

                            code_files.append(
                                {
                                    "path": file_path,
                                    "download_url": f"{base_api_url}/contents/{file_path}",
                                    "size": item.get("size", 0),
                                }
                            )

            # Trim to max_files but try to get a diverse sample
            if len(code_files) > max_files:
                # Sort by different extensions for diversity
                code_files.sort(key=lambda x: os.path.splitext(x["path"])[1])
                # Take a sampling that prioritizes diversity of file types
                selected_files = []
                ext_counts = {}

                # First pass - get one of each extension
                for file in code_files:
                    ext = os.path.splitext(file["path"])[1]
                    if ext not in ext_counts:
                        ext_counts[ext] = 1
                        selected_files.append(file)
                        if len(selected_files) >= max_files:
                            break

                # Second pass - fill remaining slots randomly
                remaining = max_files - len(selected_files)
                if remaining > 0:
                    remaining_files = [f for f in code_files if f not in selected_files]
                    selected_files.extend(
                        random.sample(
                            remaining_files, min(remaining, len(remaining_files))
                        )
                    )

                code_files = selected_files[:max_files]

            return code_files

        except Exception as e:
            print(f"Error retrieving code files: {str(e)}")
            return []

    def _get_file_content(self, download_url):
        """
        Get the content of a file from its download URL

        Args:
            download_url (str): URL to download the file

        Returns:
            str: Content of the file
        """
        try:
            response = requests.get(download_url, headers=self.headers)

            if response.status_code == 200:
                content_data = response.json()
                if (
                    "content" in content_data
                    and content_data.get("encoding") == "base64"
                ):
                    import base64

                    content = base64.b64decode(content_data["content"]).decode(
                        "utf-8", errors="replace"
                    )
                    return content

            # Try direct download if the above method fails
            raw_url = download_url.replace(
                "api.github.com/repos", "raw.githubusercontent.com"
            ).replace("/contents/", "/")
            response = requests.get(raw_url, headers=self.headers)

            if response.status_code == 200:
                return response.text

            return None

        except Exception as e:
            print(f"Error getting file content: {str(e)}")
            return None

    def _check_file_plagiarism(self, file_path, content):
        """
        Check a file for potential plagiarism using multiple methods

        Args:
            file_path (str): Path of the file
            content (str): Content of the file

        Returns:
            dict: Results of the plagiarism check
        """
        result = {
            "is_suspicious": False,
            "confidence": 0,
            "potential_source": "Unknown",
            "match_type": "None",
            "snippet": "",
        }

        # Skip very small files (likely not meaningful)
        if len(content) < 100:
            return result

        # 1. Check for specific code fingerprints/signatures
        signature_check = self._check_code_signatures(content)
        if signature_check["is_suspicious"]:
            return signature_check

        # 2. Check for copyright notices or license conflicts
        copyright_check = self._check_copyright_notices(content)
        if copyright_check["is_suspicious"]:
            return copyright_check

        # 3. Check for code snippets that are commonly copied from specific sources
        snippet_check = self._check_common_snippets(file_path, content)
        if snippet_check["is_suspicious"]:
            return snippet_check

        # 4. Apply fuzzy matching to check for slightly modified code
        # This is a simplified demo - in a real system, you'd compare against a database
        fuzzy_check = self._apply_fuzzy_matching(file_path, content)
        if fuzzy_check["is_suspicious"]:
            return fuzzy_check

        return result

    def _check_code_signatures(self, content):
        """
        Check for specific code fingerprints or signatures

        Args:
            content (str): Content of the file

        Returns:
            dict: Results of the signature check
        """
        result = {
            "is_suspicious": False,
            "confidence": 0,
            "potential_source": "Unknown",
            "match_type": "None",
            "snippet": "",
        }

        # List of signatures that might indicate plagiarism
        signatures = [
            {
                "pattern": r"Copyright \(c\) (?!.*current_year|.*repo_owner).*\d{4}",  # Copyright not matching repo owner
                "source": "Copyright notice for different author",
                "confidence": 0.7,
                "match_type": "Copyright Mismatch",
            },
            {
                "pattern": r"@author\s+(?!.*repo_owner).*",  # Author tag not matching repo owner
                "source": "Author attribution mismatch",
                "confidence": 0.6,
                "match_type": "Author Attribution",
            },
            {
                "pattern": r"DO NOT DISTRIBUTE|confidential|proprietary",  # Restricted code indicators
                "source": "Potentially proprietary code",
                "confidence": 0.8,
                "match_type": "Proprietary Code",
            },
        ]

        for signature in signatures:
            matches = re.finditer(signature["pattern"], content, re.IGNORECASE)
            for match in matches:
                snippet = content[
                    max(0, match.start() - 100) : min(len(content), match.end() + 100)
                ]
                result = {
                    "is_suspicious": True,
                    "confidence": signature["confidence"],
                    "potential_source": signature["source"],
                    "match_type": signature["match_type"],
                    "snippet": snippet,
                }
                return result

        return result

    def _check_copyright_notices(self, content):
        """
        Check for copyright notices or license conflicts

        Args:
            content (str): Content of the file

        Returns:
            dict: Results of the copyright check
        """
        result = {
            "is_suspicious": False,
            "confidence": 0,
            "potential_source": "Unknown",
            "match_type": "None",
            "snippet": "",
        }

        # Check for multiple different copyright notices in the same file
        copyright_pattern = r"Copyright\s+(?:\(c\)|©)?\s+([^,\n]+)"
        matches = re.finditer(copyright_pattern, content, re.IGNORECASE)

        copyright_holders = set()
        for match in matches:
            copyright_holder = match.group(1).strip()
            copyright_holders.add(copyright_holder)

        if len(copyright_holders) > 1:
            snippet = "; ".join(
                f"Copyright holder: {holder}" for holder in copyright_holders
            )
            result = {
                "is_suspicious": True,
                "confidence": 0.7,
                "potential_source": ", ".join(copyright_holders),
                "match_type": "Multiple Copyright Holders",
                "snippet": snippet,
            }

        return result

    def _check_common_snippets(self, file_path, content):
        """
        Check for code snippets that are commonly copied

        Args:
            file_path (str): Path of the file
            content (str): Content of the file

        Returns:
            dict: Results of the common snippet check
        """
        result = {
            "is_suspicious": False,
            "confidence": 0,
            "potential_source": "Unknown",
            "match_type": "None",
            "snippet": "",
        }

        # Common snippets often copied from specific sources
        # This is a simplified version - a real system would have a larger database
        common_snippets = [
            {
                "pattern": r"def quicksort\(arr\):\s+if len\(arr\) <= 1:\s+return arr",
                "source": "Common QuickSort implementation from GeeksforGeeks",
                "confidence": 0.5,
                "match_type": "Algorithm Implementation",
                "extension": ".py",
            },
            {
                "pattern": r"function debounce\(func, wait\)",
                "source": "Common JavaScript utility from Underscore.js or Lodash",
                "confidence": 0.6,
                "match_type": "Utility Function",
                "extension": ".js",
            },
            {
                "pattern": r"public\s+static\s+void\s+main\(String\[\]\s+args\)",
                "source": "Standard Java main method - not plagiarism on its own",
                "confidence": 0.2,
                "match_type": "Standard Boilerplate",
                "extension": ".java",
            },
        ]

        file_ext = os.path.splitext(file_path)[1].lower()

        for snippet in common_snippets:
            if snippet.get("extension") and snippet["extension"] != file_ext:
                continue

            if re.search(snippet["pattern"], content):
                # If it's a very common pattern with low confidence, don't flag it
                if snippet["confidence"] <= 0.3:
                    continue

                # Find the matched text with some context
                match = re.search(snippet["pattern"], content)
                context = content[
                    max(0, match.start() - 100) : min(len(content), match.end() + 100)
                ]

                result = {
                    "is_suspicious": True,
                    "confidence": snippet["confidence"],
                    "potential_source": snippet["source"],
                    "match_type": snippet["match_type"],
                    "snippet": context,
                }
                return result

        return result

    def _apply_fuzzy_matching(self, file_path, content):
        """
        Apply fuzzy matching to check for slightly modified code

        Args:
            file_path (str): Path of the file
            content (str): Content of the file

        Returns:
            dict: Results of the fuzzy matching
        """
        result = {
            "is_suspicious": False,
            "confidence": 0,
            "potential_source": "Unknown",
            "match_type": "None",
            "snippet": "",
        }

        # In a real system, this would compare against a database of known code
        # For this demo, we'll check against some very common code patterns

        # Normalize the content to make comparison more effective
        normalized_content = self._normalize_code(content, file_path)

        # Check for abnormally high entropy in variable names (potential obfuscation)
        if self._check_obfuscation(normalized_content):
            result = {
                "is_suspicious": True,
                "confidence": 0.7,
                "potential_source": "Unknown - Potentially obfuscated code",
                "match_type": "Possible Obfuscation",
                "snippet": "Variable/function names appear randomly generated, suggesting possible obfuscation.",
            }
            return result

        return result

    def _normalize_code(self, content, file_path):
        """
        Normalize code for better comparison (remove comments, whitespace, etc.)

        Args:
            content (str): Content of the file
            file_path (str): Path of the file

        Returns:
            str: Normalized code
        """
        # Get file extension
        ext = os.path.splitext(file_path)[1].lower()

        # Remove comments based on language
        if ext in [".py"]:
            # Remove Python comments
            content = re.sub(r"#.*$", "", content, flags=re.MULTILINE)
            content = re.sub(r'""".*?"""', "", content, flags=re.DOTALL)
            content = re.sub(r"'''.*?'''", "", content, flags=re.DOTALL)
        elif ext in [".js", ".java", ".c", ".cpp", ".cs"]:
            # Remove C-style comments
            content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
            content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

        # Remove whitespace
        content = re.sub(r"\s+", " ", content)

        return content

    def _check_obfuscation(self, content):
        """
        Check for signs of code obfuscation

        Args:
            content (str): Content of the file

        Returns:
            bool: True if obfuscation is suspected, False otherwise
        """
        # Extract variable and function names
        var_pattern = r"\b(var|let|const|function|class|def|int|string|boolean|float|double)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b"
        names = re.findall(var_pattern, content)

        if not names:
            return False

        # Extract just the names without the type
        names = [name[1] for name in names]

        # Check for random-looking names (high entropy)
        random_looking_names = 0
        for name in names:
            # Skip very short names
            if len(name) < 4:
                continue

            # Calculate entropy of the name
            entropy = self._calculate_entropy(name)

            # High entropy names might indicate obfuscation
            if entropy > 3.5 and not self._is_common_name(name):
                random_looking_names += 1

        # If more than 30% of names look random, flag as suspicious
        return random_looking_names > 0 and (random_looking_names / len(names)) > 0.3

    def _calculate_entropy(self, text):
        """
        Calculate the entropy of a string (measure of randomness)

        Args:
            text (str): The string to analyze

        Returns:
            float: Entropy value
        """
        # Count each character
        counts = {}
        for char in text:
            counts[char] = counts.get(char, 0) + 1

        # Calculate entropy
        length = len(text)
        entropy = 0

        for count in counts.values():
            probability = count / length
            entropy -= probability * (1 / probability)

        return entropy

    def _is_common_name(self, name):
        """
        Check if a name is a common programming name

        Args:
            name (str): The name to check

        Returns:
            bool: True if it's a common name, False otherwise
        """
        common_names = [
            "index",
            "count",
            "value",
            "result",
            "temp",
            "data",
            "array",
            "string",
            "number",
            "object",
            "element",
            "node",
            "item",
            "response",
            "request",
            "message",
            "buffer",
            "stream",
            "file",
            "input",
            "output",
            "error",
            "logger",
            "handler",
            "helper",
            "util",
            "factory",
            "manager",
            "service",
            "provider",
            "model",
            "view",
            "controller",
            "component",
            "container",
            "wrapper",
        ]

        return name.lower() in common_names
