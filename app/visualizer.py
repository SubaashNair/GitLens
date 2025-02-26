# app/visualizer.py
import matplotlib.pyplot as plt
import networkx as nx
import io
import base64
from matplotlib.colors import LinearSegmentedColormap
import numpy as np


def generate_dependency_graph(dependency_data: dict, max_nodes: int = 30) -> str:
    """
    Generate a dependency graph visualization from dependency analysis data

    Args:
        dependency_data (dict): Output from DependencyAnalyzer
        max_nodes (int): Maximum number of nodes to show for readability

    Returns:
        str: Base64 encoded PNG image of the graph
    """
    # Create a directed graph
    G = nx.DiGraph()

    # Add nodes and edges based on import relationships
    imports = dependency_data.get("imports", {})
    imported_by = dependency_data.get("imported_by", {})

    # Combine all files that have import relationships
    all_files = set()
    for file, deps in imports.items():
        if deps:  # Only include if it has dependencies
            all_files.add(file)

    for file, deps in imported_by.items():
        if deps:  # Only include if it's imported by others
            all_files.add(file)
            for dep in deps:
                all_files.add(dep)

    # If we have too many files, prioritize key files
    if len(all_files) > max_nodes:
        # Use key files identified by centrality
        key_files = [f[0] for f in dependency_data.get("key_files", [])]

        # Also include entry points
        entry_points = dependency_data.get("entry_points", [])

        # Combine key files and entry points, up to max_nodes
        priority_files = set(key_files + entry_points)

        # If still not enough, add files with most dependencies/dependents
        if len(priority_files) < max_nodes:
            # Sort files by total connections (imports + imported by)
            connection_counts = {}
            for file in all_files:
                import_count = len(imports.get(file, []))
                imported_by_count = len(imported_by.get(file, []))
                connection_counts[file] = import_count + imported_by_count

            sorted_files = sorted(
                connection_counts.items(), key=lambda x: x[1], reverse=True
            )
            for file, _ in sorted_files:
                if file not in priority_files:
                    priority_files.add(file)
                    if len(priority_files) >= max_nodes:
                        break

        all_files = priority_files

    # Clean up file paths for better readability
    def clean_path(path):
        # Keep the last 3 parts of the path at most for readability
        parts = path.split("/")
        if len(parts) > 3:
            return "/".join([".."] + parts[-3:])
        return path

    # Add nodes to graph
    for file in all_files:
        G.add_node(clean_path(file))

    # Add edges only between files that are in our filtered set
    for file in all_files:
        clean_file = clean_path(file)
        # Add edges for imports
        for import_file in imports.get(file, []):
            for target in all_files:
                # Simple heuristic: if import name is in target path
                if import_file in target:
                    G.add_edge(clean_file, clean_path(target))

    # Create a larger figure for better readability
    plt.figure(figsize=(12, 10))

    # Use a nicer color scheme
    cmap = plt.cm.plasma

    # Calculate node sizes based on connectivity
    node_sizes = []
    node_colors = []

    for node in G.nodes():
        in_degree = G.in_degree(node) + 1  # Files imported by others
        out_degree = G.out_degree(node) + 1  # Files that this imports

        # Size based on total connections
        node_sizes.append(300 * np.log(in_degree + out_degree))

        # Color based on ratio of in to out degree (importers vs importees)
        if in_degree > out_degree:
            # More imported by others than imports - bluer
            node_colors.append(0.3)
        elif out_degree > in_degree:
            # Imports more than imported by others - redder
            node_colors.append(0.7)
        else:
            # Balanced - purple
            node_colors.append(0.5)

    # Create layout - try to minimize edge crossings
    try:
        pos = nx.spring_layout(G, k=0.15, iterations=50)
    except:
        try:
            pos = nx.shell_layout(G)
        except:
            pos = nx.random_layout(G)

    # Draw the graph
    nx.draw_networkx_nodes(
        G, pos, node_size=node_sizes, node_color=node_colors, cmap=cmap, alpha=0.8
    )
    nx.draw_networkx_edges(
        G, pos, edge_color="gray", arrows=True, arrowsize=15, alpha=0.6
    )
    nx.draw_networkx_labels(G, pos, font_size=8, font_color="black", font_weight="bold")

    plt.title("Code Dependency Graph", fontsize=16, fontweight="bold")

    # Add legend
    plt.text(
        0.01,
        0.01,
        "Blue: Imported by others\nRed: Imports others\nSize: Total connections",
        transform=plt.gca().transAxes,
        fontsize=10,
        verticalalignment="bottom",
    )

    plt.axis("off")
    plt.tight_layout()

    # Save the figure to a BytesIO object
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300)
    plt.close()

    # Encode the image to base64 for HTML display
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode("utf-8")

    return f"data:image/png;base64,{img_str}"


def generate_dependency_summary(dependency_data: dict) -> str:
    """
    Generate a text summary of the dependency analysis

    Args:
        dependency_data (dict): Output from DependencyAnalyzer

    Returns:
        str: Markdown formatted summary
    """
    metrics = dependency_data.get("metrics", {})
    key_files = dependency_data.get("key_files", [])
    entry_points = dependency_data.get("entry_points", [])
    isolated_files = dependency_data.get("isolated_files", [])
    extension_counts = dependency_data.get("extension_counts", {})

    summary = "## Code Dependency Analysis\n\n"

    # Add file type breakdown
    summary += "### File Type Distribution\n"
    for ext, count in sorted(
        extension_counts.items(), key=lambda x: x[1], reverse=True
    ):
        if count > 0:
            summary += f"- {ext}: {count} files\n"

    # Add dependency metrics
    summary += "\n### Dependency Metrics\n"
    summary += f"- Total files analyzed: {metrics.get('total_files', 0)}\n"
    summary += (
        f"- Average dependencies per file: {metrics.get('avg_dependencies', 0):.2f}\n"
    )
    summary += f"- Maximum dependencies: {metrics.get('max_dependencies', 0)} (in {metrics.get('file_with_max_dependencies', 'N/A')})\n"
    summary += (
        f"- Average dependents per file: {metrics.get('avg_dependents', 0):.2f}\n"
    )
    summary += f"- Maximum dependents: {metrics.get('max_dependents', 0)} (for {metrics.get('file_with_max_dependents', 'N/A')})\n"

    # Add key files section
    if key_files:
        summary += "\n### Key Files (Highest Centrality)\n"
        for file, centrality in key_files[:5]:  # Show top 5
            summary += f"- {file} (centrality: {centrality:.3f})\n"

    # Add entry points
    if entry_points:
        summary += "\n### Potential Entry Points\n"
        for file in entry_points[:5]:  # Show top 5
            summary += f"- {file}\n"

        if len(entry_points) > 5:
            summary += f"- ... and {len(entry_points) - 5} more\n"

    # Add isolated files if there are any
    if isolated_files:
        summary += "\n### Isolated Files (No Dependencies)\n"
        for file in isolated_files[:5]:  # Show top 5
            summary += f"- {file}\n"

        if len(isolated_files) > 5:
            summary += f"- ... and {len(isolated_files) - 5} more\n"

    return summary
