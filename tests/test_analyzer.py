import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import time

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.analyzer import analyze_repo, identify_frameworks, analyze_code_quality


class TestAnalyzer(unittest.TestCase):
    """Test cases for the repository analyzer module"""

    @patch('app.analyzer.requests.get')
    def test_analyze_repo_handles_rate_limit(self, mock_get):
        """Test that analyze_repo handles GitHub API rate limits properly"""
        # Set up the mock to simulate a rate limit exceeded response followed by success
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.text = "API rate limit exceeded"
        
        # Mock for rate_info response
        rate_info_response = MagicMock()
        rate_info_response.status_code = 200
        rate_info_response.json.return_value = {
            "resources": {
                "core": {
                    "limit": 60,
                    "remaining": 0,
                    "reset": int(time.time()) + 60
                }
            }
        }
        
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "name": "test-repo", 
            "description": "A test repository",
            "stargazers_count": 10,
            "forks_count": 5
        }
        
        # Configure the mock to return different responses on consecutive calls
        # This accounts for initial API call, rate info call, and retry
        mock_get.side_effect = [rate_limit_response, rate_info_response, success_response, success_response]
        
        # Mock multiple dependencies to isolate the test
        with patch('app.analyzer.time.sleep', return_value=None):
            with patch('app.analyzer.get_folder_structure_with_contents', return_value=("folder structure", {})):
                with patch('app.utils.get_cached_repository_data', return_value=None):
                    with patch('app.utils.cache_repository_data'):
                        with patch('app.utils.cache_file_content'):
                            try:
                                result = analyze_repo("https://github.com/test/repo", max_file_size=1000, file_limit=5)
                                self.assertIn("folder_structure", result)
                                self.assertIn("frameworks", result)
                            except Exception as e:
                                self.fail(f"analyze_repo raised exception {e} when it should have handled rate limits")

    def test_identify_frameworks(self):
        """Test that frameworks are correctly identified from folder structure"""
        folder_structure = """
        📁 /src/
            📄 package.json
            📄 app.js
            📁 components/
                📄 Button.jsx
            📁 styles/
                📄 main.css
        📁 /tests/
            📄 test.js
        """
        
        frameworks = identify_frameworks(folder_structure)
        
        # Check that Node.js and React are detected
        self.assertIn("Node.js", frameworks)
        self.assertIn("JavaScript", frameworks)
        
        # Test with file contents
        file_contents = {
            "src/app.js": "import React from 'react';\nconst express = require('express');",
            "package.json": '{"dependencies": {"react": "^17.0.2", "express": "^4.17.1"}}'
        }
        
        frameworks = identify_frameworks(folder_structure, file_contents)
        self.assertIn("React", frameworks)
        self.assertIn("Express", frameworks)

    def test_analyze_code_quality(self):
        """Test that code quality metrics are correctly analyzed"""
        file_contents = {
            "test.py": "def hello():\n    return 'Hello World'\n\n# A comment\n",
            "large.js": "// " + "x" * 510 + "\n" * 510  # Create a large file with 510 lines
        }
        
        metrics = analyze_code_quality(file_contents)
        
        # Verify basic metrics
        self.assertEqual(metrics["total_files"], 2)
        self.assertTrue(metrics["total_lines"] > 510)
        self.assertGreater(metrics["blank_lines"], 0)
        
        # Check that large.js is identified as a large file
        large_files = [f["path"] for f in metrics["large_files"]]
        self.assertIn("large.js", large_files)


if __name__ == "__main__":
    unittest.main()