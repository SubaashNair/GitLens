# app/dependency_analyzer.py
import re
import os
import networkx as nx
from collections import defaultdict


class DependencyAnalyzer:
    def __init__(self):
        self.import_patterns = {
            # Python imports
            ".py": [
                r"^\s*import\s+([a-zA-Z0-9_.,\s]+)",
                r"^\s*from\s+([a-zA-Z0-9_.]+)\s+import",
            ],
            # JavaScript/TypeScript imports
            ".js": [
                r'^\s*import\s+.*\s+from\s+[\'"](.+?)[\'"]',
                r'^\s*const\s+.*\s+=\s+require\([\'"](.+?)[\'"]\)',
            ],
            ".jsx": [
                r'^\s*import\s+.*\s+from\s+[\'"](.+?)[\'"]',
                r'^\s*const\s+.*\s+=\s+require\([\'"](.+?)[\'"]\)',
            ],
            ".ts": [
                r'^\s*import\s+.*\s+from\s+[\'"](.+?)[\'"]',
                r'^\s*const\s+.*\s+=\s+require\([\'"](.+?)[\'"]\)',
            ],
            ".tsx": [
                r'^\s*import\s+.*\s+from\s+[\'"](.+?)[\'"]',
                r'^\s*const\s+.*\s+=\s+require\([\'"](.+?)[\'"]\)',
            ],
            # Java imports
            ".java": [
                r"^\s*import\s+([a-zA-Z0-9_.]+);",
            ],
            # C/C++ includes
            ".c": [
                r'^\s*#include\s+[<"](.+?)[>"]',
            ],
            ".cpp": [
                r'^\s*#include\s+[<"](.+?)[>"]',
            ],
            ".h": [
                r'^\s*#include\s+[<"](.+?)[>"]',
            ],
            # PHP includes/requires
            ".php": [
                r'(include|require|include_once|require_once)\s*\(\s*[\'"](.+?)[\'"]\s*\)',
                r'(include|require|include_once|require_once)\s+[\'"](.+?)[\'"]\s*;',
            ],
            # Ruby requires
            ".rb": [
                r'^\s*require\s+[\'"](.+?)[\'"]',
                r'^\s*require_relative\s+[\'"](.+?)[\'"]',
            ],
        }

        # Default patterns for any file type not specified above
        self.default_patterns = [
            r'import\s+[\'"](.+?)[\'"]',
            r'require\([\'"](.+?)[\'"]\)',
            r'include\s+[\'"](.+?)[\'"]',
        ]

        # Function/class definition patterns
        self.definition_patterns = {
            ".py": [
                r"^\s*def\s+([a-zA-Z0-9_]+)\s*\(",  # Function
                r"^\s*class\s+([a-zA-Z0-9_]+)\s*",  # Class
                r"^\s*async\s+def\s+([a-zA-Z0-9_]+)\s*\(",  # Async function
            ],
            ".js": [
                r"^\s*function\s+([a-zA-Z0-9_]+)\s*\(",  # Function
                r"^\s*class\s+([a-zA-Z0-9_]+)",  # Class
                r"^\s*const\s+([a-zA-Z0-9_]+)\s*=\s*\([^)]*\)\s*=>",  # Arrow function
                r"^\s*const\s+([a-zA-Z0-9_]+)\s*=\s*function",  # Function expression
            ],
            ".java": [
                r"^\s*(public|private|protected)?\s*(static)?\s*[a-zA-Z0-9_<>]+\s+([a-zA-Z0-9_]+)\s*\(",  # Method
                r"^\s*(public|private|protected)?\s*(static)?\s*class\s+([a-zA-Z0-9_]+)",  # Class
                r"^\s*(public|private|protected)?\s*interface\s+([a-zA-Z0-9_]+)",  # Interface
            ],
            ".php": [
                r"^\s*function\s+([a-zA-Z0-9_]+)\s*\(",  # Function
                r"^\s*class\s+([a-zA-Z0-9_]+)",  # Class
            ],
        }

    def analyze_dependencies(self, file_contents: dict) -> dict:
        """
        Analyze dependencies between files in a repository

        Args:
            file_contents (dict): Dictionary mapping file paths to their contents

        Returns:
            dict: Dictionary containing dependency information
        """
        # Initialize dependency tracking
        imports = {}  # What each file imports
        imported_by = defaultdict(list)  # Which files import this file
        definitions = {}  # Functions/classes defined in each file

        # Track file extensions for summary
        extension_counts = defaultdict(int)

        # Process each file
        for file_path, content in file_contents.items():
            file_ext = os.path.splitext(file_path)[1].lower()
            extension_counts[file_ext] += 1

            # Get file-specific patterns or use default
            import_patterns = self.import_patterns.get(file_ext, self.default_patterns)
            definition_patterns = self.definition_patterns.get(file_ext, [])

            # Extract imports
            file_imports = []
            for pattern in import_patterns:
                for line in content.split("\n"):
                    matches = re.findall(pattern, line)
                    if matches:
                        for match in matches:
                            # Handle PHP patterns which may have multiple groups
                            if isinstance(match, tuple) and len(match) > 1:
                                match = match[
                                    1
                                ]  # Use the second group which contains the file path

                            # Clean up the match
                            if isinstance(match, str):
                                import_name = match.strip()
                                if import_name:
                                    file_imports.append(import_name)

            imports[file_path] = file_imports

            # Update imported_by
            for import_name in file_imports:
                # Look for files that match the import
                for potential_file in file_contents.keys():
                    # Handle Python relative imports
                    if file_ext == ".py":
                        module_name = os.path.splitext(
                            os.path.basename(potential_file)
                        )[0]
                        package_path = os.path.dirname(potential_file).replace("/", ".")

                        if (
                            import_name == module_name
                            or import_name == package_path
                            or import_name.endswith("." + module_name)
                            or package_path.endswith("." + import_name)
                        ):
                            imported_by[potential_file].append(file_path)

                    # Handle JavaScript/TypeScript relative imports
                    elif file_ext in [".js", ".jsx", ".ts", ".tsx"]:
                        # Remove extension and handle relative paths
                        if import_name.startswith("./") or import_name.startswith(
                            "../"
                        ):
                            # Convert relative path to absolute (simplified)
                            base_dir = os.path.dirname(file_path)
                            import_path = os.path.normpath(
                                os.path.join(base_dir, import_name)
                            )

                            # Check if potential_file matches the import path
                            if potential_file.startswith(
                                import_path
                            ) or import_path.startswith(potential_file):
                                imported_by[potential_file].append(file_path)

                    # Simple substring match for other types
                    elif import_name in potential_file:
                        imported_by[potential_file].append(file_path)

            # Extract function/class definitions
            file_definitions = []
            for pattern in definition_patterns:
                for line in content.split("\n"):
                    matches = re.findall(pattern, line)
                    if matches:
                        for match in matches:
                            # Handle patterns which may have multiple groups
                            if isinstance(match, tuple):
                                # For Java patterns, the class/method name is in the last group
                                match = match[-1]

                            if isinstance(match, str):
                                def_name = match.strip()
                                if def_name:
                                    file_definitions.append(def_name)

            definitions[file_path] = file_definitions

        # Build a dependency graph
        graph = nx.DiGraph()

        # Add all files as nodes
        for file_path in file_contents.keys():
            graph.add_node(file_path)

        # Add dependency edges
        for file_path, file_imports in imports.items():
            for import_name in file_imports:
                for target_file in file_contents.keys():
                    # Simple heuristic: if the import name is in the target file path
                    if import_name in target_file:
                        graph.add_edge(file_path, target_file)

        # Identify key files (high centrality)
        try:
            centrality = nx.betweenness_centrality(graph)
            key_files = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        except:
            key_files = []

        # Identify entry points (files not imported by others)
        entry_points = [
            file
            for file in file_contents.keys()
            if file not in imported_by or not imported_by[file]
        ]

        # Find isolated files (not importing or imported by others)
        isolated_files = [
            file
            for file in file_contents.keys()
            if (file not in imports or not imports[file])
            and (file not in imported_by or not imported_by[file])
        ]

        # Compute dependency metrics
        try:
            avg_dependencies = (
                sum(len(deps) for deps in imports.values()) / len(imports)
                if imports
                else 0
            )
            max_dependencies = (
                max(len(deps) for deps in imports.values()) if imports else 0
            )
            file_with_max_dependencies = (
                max(imports.items(), key=lambda x: len(x[1]))[0] if imports else None
            )

            avg_dependents = (
                sum(len(deps) for deps in imported_by.values()) / len(imported_by)
                if imported_by
                else 0
            )
            max_dependents = (
                max(len(deps) for deps in imported_by.values()) if imported_by else 0
            )
            file_with_max_dependents = (
                max(imported_by.items(), key=lambda x: len(x[1]))[0]
                if imported_by
                else None
            )
        except:
            avg_dependencies = 0
            max_dependencies = 0
            file_with_max_dependencies = None
            avg_dependents = 0
            max_dependents = 0
            file_with_max_dependents = None

        # Return the analysis results
        return {
            "imports": imports,
            "imported_by": dict(imported_by),  # Convert defaultdict to dict
            "definitions": definitions,
            "extension_counts": dict(extension_counts),
            "key_files": key_files,
            "entry_points": entry_points,
            "isolated_files": isolated_files,
            "metrics": {
                "total_files": len(file_contents),
                "avg_dependencies": avg_dependencies,
                "max_dependencies": max_dependencies,
                "file_with_max_dependencies": file_with_max_dependencies,
                "avg_dependents": avg_dependents,
                "max_dependents": max_dependents,
                "file_with_max_dependents": file_with_max_dependents,
            },
        }
