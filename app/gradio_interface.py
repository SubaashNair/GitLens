# # mark3 with plagiarism
# import gradio as gr
# import requests
# import json
# import time
# import threading
# import asyncio
# from app.plagiarism_detector import PlagiarismDetector
# from app.analyzer import analyze_repo
# from app.utils import load_env

# # Load environment variables
# load_env()


# class RepoChat:
#     def __init__(self):
#         self.repo_analysis = None
#         self.chat_history = []
#         self.is_analyzing = False
#         self.plagiarism_results = None

#     def analyze_repository_with_progress(
#         self,
#         repo_url,
#         github_token=None,
#         check_plagiarism=False,
#         progress=gr.Progress(),
#     ):
#         """Analyze the repository with progress tracking"""
#         self.is_analyzing = True
#         progress(0, desc="Starting repository analysis...")

#         try:
#             # Track the start time
#             start_time = time.time()

#             # Simulate progress updates during analysis
#             # Since analyze_repo doesn't provide progress updates, we'll simulate them
#             def update_progress():
#                 steps = 5
#                 for i in range(1, steps + 1):
#                     if not self.is_analyzing:
#                         break
#                     time.sleep(0.5)  # Delay between updates
#                     progress(i / steps, desc=f"Analyzing repository: Phase {i}/{steps}")

#             # Start progress updates in a separate thread
#             progress_thread = threading.Thread(target=update_progress)
#             progress_thread.start()

#             # Actually analyze the repository, passing the GitHub token if provided
#             try:
#                 self.repo_analysis = analyze_repo(
#                     repo_url, github_token=github_token if github_token else None
#                 )
#             except Exception as e:
#                 if "rate limit exceeded" in str(e).lower():
#                     raise Exception(
#                         f"GitHub API rate limit exceeded. Please provide a GitHub token or try again later. Error: {str(e)}"
#                     )
#                 else:
#                     raise e

#             # Check for plagiarism if requested
#             if check_plagiarism:
#                 progress(0.6, desc="Checking for potential plagiarism...")
#                 plagiarism_detector = PlagiarismDetector(github_token=github_token)
#                 self.plagiarism_results = plagiarism_detector.detect_plagiarism(
#                     repo_url
#                 )
#             else:
#                 self.plagiarism_results = None

#             # Stop the progress updates
#             self.is_analyzing = False
#             progress_thread.join()

#             # Calculate time taken
#             elapsed_time = time.time() - start_time

#             # Get the analysis results
#             folder_structure = self.repo_analysis["folder_structure"]
#             frameworks = self.repo_analysis["frameworks"]
#             additional_info = self.repo_analysis.get("additional_info", "")

#             # Format the repository analysis as markdown for better display
#             analysis_markdown = f"""
# ## Repository Analysis Results
# *Analysis completed in {elapsed_time:.2f} seconds*

# ### Folder Structure
# ```
# {folder_structure}
# ```
# """

#             # Add plagiarism information if available
#             if self.plagiarism_results:
#                 analysis_markdown += f"""
# ### Plagiarism Check Results
# {self.plagiarism_results['summary']}

# """
#                 if self.plagiarism_results["plagiarism_detected"]:
#                     analysis_markdown += "#### Suspicious Files:\n"
#                     for file in self.plagiarism_results["suspicious_files"]:
#                         analysis_markdown += f"- **{file['file']}** - {file['match_type']} (Confidence: {int(file['confidence']*100)}%)\n"
#                         analysis_markdown += (
#                             f"  - Potential source: {file['potential_source']}\n"
#                         )

#             # Store frameworks and additional info for chat suggestions
#             self.frameworks_info = frameworks
#             self.additional_info = additional_info

#             # Reset chat history with the system message and initial suggestions
#             self.chat_history = []

#             # Create initial suggestions message
#             suggestions = "**Repository Analysis Complete!** Here are some questions you might want to ask:\n\n"

#             if frameworks:
#                 suggestions += (
#                     "- What frameworks/technologies are used in this repository?\n"
#                 )
#                 suggestions += "- Can you explain the purpose of the main frameworks?\n"

#             suggestions += "- What is the main purpose of this repository?\n"
#             suggestions += "- Can you explain the overall architecture?\n"
#             suggestions += "- Are there any security concerns in this codebase?\n"

#             if (
#                 self.plagiarism_results
#                 and self.plagiarism_results["plagiarism_detected"]
#             ):
#                 suggestions += (
#                     "- Can you explain more about the potentially plagiarized code?\n"
#                 )

#             suggestions += "- How can I contribute to this project?\n"

#             # Return both the analysis markdown and the suggestions for the chatbot in tuple format
#             return analysis_markdown, [(None, suggestions)]

#         except Exception as e:
#             error_message = f"Error analyzing repository: {str(e)}"
#             self.chat_history = []
#             self.is_analyzing = False
#             if "progress_thread" in locals() and progress_thread.is_alive():
#                 progress_thread.join()
#             progress(1.0, desc="Analysis failed!")
#             return error_message, [
#                 (None, "Error analyzing repository. Please try again.")
#             ]

#     def query_claude(self, user_message, progress=gr.Progress(), status_updates=None):
#         """Send a query to Claude API with the repository context and chat history"""
#         if not self.repo_analysis:
#             return "Please analyze a repository first."

#         # Use the status updates if provided, otherwise use the progress bar
#         if status_updates:
#             current_status = status_updates[0]
#         else:
#             progress(0.1, desc="Preparing request...")
#             current_status = "Preparing request..."

#         # For debugging - print API information instead of showing to user
#         print(f"Starting Claude API request for message: {user_message[:50]}...")

#         # Get API key from environment variables
#         api_key = load_env().get("API_KEY")

#         if not api_key:
#             return "Error: API_KEY not found in environment variables"

#         # Create system message with repository context
#         system_message = (
#             f"You are assisting with a GitHub repository analysis. Here is the information about the repository:\n\n"
#             f"Folder Structure:\n{self.repo_analysis['folder_structure']}\n\n"
#             f"Frameworks:\n{self.repo_analysis['frameworks']}\n\n"
#             f"Additional Analysis:\n{self.repo_analysis.get('additional_info', '')}\n\n"
#         )

#         # Add plagiarism information if available
#         if self.plagiarism_results:
#             system_message += (
#                 f"Plagiarism Check Results:\n{self.plagiarism_results['summary']}\n\n"
#             )

#             if self.plagiarism_results["plagiarism_detected"]:
#                 system_message += "Suspicious Files:\n"
#                 for file in self.plagiarism_results["suspicious_files"]:
#                     system_message += (
#                         f"- {file['file']} - {file['match_type']} (Confidence: {int(file['confidence']*100)}%)\n"
#                         f"  Potential source: {file['potential_source']}\n"
#                         f"  Snippet: {file['snippet']}\n\n"
#                     )

#         system_message += (
#             f"While you have all this information, the user only sees the folder structure and a summary of plagiarism results if performed. "
#             f"If they ask about frameworks or technologies, explain them based on the frameworks information I've provided to you. "
#             f"Similarly, use the additional analysis information when relevant, but don't directly mention that you were given this data separately. "
#             f"If they ask about plagiarism, provide insights based on the plagiarism check results if available."
#         )

#         if status_updates and len(status_updates) > 1:
#             current_status = status_updates[1]
#         else:
#             progress(0.3, desc="Building message context...")
#             current_status = "Building message context..."

#         # Prepare messages for Claude API (without the system role)
#         messages = []

#         # Add chat history to the messages (limit to last 10 exchanges to avoid token limits)
#         for human_msg, ai_msg in self.chat_history[-10:]:
#             if human_msg is not None:  # Skip system messages
#                 messages.append({"role": "user", "content": human_msg})
#                 messages.append({"role": "assistant", "content": ai_msg})

#         # Add the current user message
#         messages.append({"role": "user", "content": user_message})

#         # Prepare the payload for Claude API - correcting payload format
#         payload = {
#             "model": "claude-3-7-sonnet-20250219",
#             "max_tokens": 1000,
#             "system": system_message,  # Use top-level system parameter instead of in messages
#             "messages": messages,
#             "temperature": 0.7,
#         }

#         # Set headers with API key - using correct header format
#         headers = {
#             "x-api-key": api_key,
#             "anthropic-version": "2023-06-01",
#             "content-type": "application/json",
#         }

#         # For debugging - print the request payload instead of showing to user
#         print(
#             "Sending request to Claude API with payload:", json.dumps(payload, indent=2)
#         )

#         if status_updates and len(status_updates) > 2:
#             current_status = status_updates[2]
#         else:
#             progress(0.5, desc="Sending request to Claude API...")
#             current_status = "Sending request to Claude API..."

#         # Send the request to the Claude API
#         try:
#             response = requests.post(
#                 "https://api.anthropic.com/v1/messages", json=payload, headers=headers
#             )

#             # For debugging - print response status and headers instead of showing to user
#             print(f"Response status: {response.status_code}")
#             print(
#                 f"Response: {response.text[:1000]}"
#             )  # Print first 1000 chars of response

#             response.raise_for_status()

#             if not status_updates:
#                 progress(0.8, desc="Processing response...")

#             # Extract the response content
#             result = response.json()
#             if "content" in result and len(result["content"]) > 0:
#                 claude_response = result["content"][0]["text"]

#                 # Update chat history
#                 self.chat_history.append((user_message, claude_response))

#                 if not status_updates:
#                     progress(1.0, desc="Response ready!")
#                 return claude_response
#             else:
#                 if not status_updates:
#                     progress(1.0, desc="No response content!")
#                 return "No response content from Claude."

#         except requests.exceptions.RequestException as e:
#             if not status_updates:
#                 progress(1.0, desc="Error!")
#             error_details = (
#                 response.text if "response" in locals() else "No response details"
#             )
#             print(f"API Error details: {error_details}")
#             return f"Error querying Claude API: {str(e)}\n\nDetails: {error_details}"

#     def chat(self, user_message, history, progress=gr.Progress()):
#         """Process a chat message and update the history"""
#         if not user_message.strip():
#             return history, "Please enter a question."

#         # Return status updates to the dedicated status area instead of using progress popup
#         status_updates = [
#             "Processing your question...",
#             "Sending request to Claude API...",
#             "Waiting for response...",
#         ]

#         # Use the first status update instead of progress popup
#         # progress(0.1, desc=status_updates[0])
#         response = self.query_claude(
#             user_message, progress, status_updates=status_updates
#         )

#         # Ensure we're using the tuple format that matches the chatbot type
#         history.append((user_message, response))

#         # Also update the internal chat history for the API
#         self.chat_history.append((user_message, response))

#         # Return ready status after completion
#         return history, "Ready to answer more questions."

#     def get_full_conversation(self):
#         """Return the full conversation history in a copyable format"""
#         if not self.chat_history:
#             return "No conversation history available."

#         conversation = []
#         for user_msg, claude_msg in self.chat_history:
#             conversation.append(f"User: {user_msg}")
#             conversation.append(f"Claude: {claude_msg}")
#             conversation.append("---")

#         return "\n\n".join(conversation)


# def launch_app():
#     repo_chat = RepoChat()

#     with gr.Blocks(theme=gr.themes.Soft()) as demo:
#         gr.Markdown("# GitLens - Github Repo Chat Assistant")

#         with gr.Row():
#             with gr.Column(scale=3):
#                 repo_input = gr.Textbox(
#                     label="Enter GitHub Repository URL",
#                     placeholder="https://github.com/username/repository",
#                 )
#             with gr.Column(scale=2):
#                 github_token = gr.Textbox(
#                     label="GitHub Token (Optional)",
#                     placeholder="ghp_xxxxxxxxxxxx",
#                     type="password",
#                     info="Avoids rate limiting. Create one at github.com/settings/tokens",
#                 )
#             with gr.Column(scale=1):
#                 analyze_button = gr.Button("Analyze Repository", variant="primary")

#         # Options for analysis
#         with gr.Row():
#             check_plagiarism = gr.Checkbox(
#                 label="Check for potential plagiarism", value=False
#             )

#         # Analysis status indicator
#         analysis_status = gr.Markdown(
#             "Enter a repository URL and click 'Analyze Repository' to begin."
#         )

#         # Repository analysis section with copy button
#         with gr.Accordion("Repository Analysis", open=True):
#             repo_analysis_output = gr.Markdown(label="Analysis Results")

#         # Chatbot interface with consistent type
#         with gr.Accordion("Chat with Repository Assistant", open=True):
#             # Add a dedicated status area above the chatbot
#             chat_status = gr.Markdown("Ready to answer questions about the repository.")

#             chatbot = gr.Chatbot(
#                 label="Chat with Claude about this repository",
#                 height=400,
#                 show_copy_button=True,
#                 type="tuples",  # Keep using tuples to avoid format mismatch issues
#             )

#             with gr.Row():
#                 with gr.Column(scale=4):
#                     msg = gr.Textbox(
#                         label="Ask about the repository",
#                         placeholder="What is the main purpose of this repository?",
#                         lines=2,
#                     )
#                 with gr.Column(scale=1):
#                     submit_btn = gr.Button("Send", variant="primary")

#             # Add buttons for chat management
#             with gr.Row():
#                 clear_btn = gr.Button("Clear Chat")
#                 export_btn = gr.Button("Export Conversation")

#         # Export conversation output
#         with gr.Accordion("Conversation Export", open=False):
#             conversation_output = gr.TextArea(
#                 label="Full Conversation",
#                 lines=10,
#                 placeholder="Your conversation will appear here after clicking 'Export Conversation'",
#                 interactive=False,
#             )
#             copy_btn = gr.Button("Copy to Clipboard")

#         # Set up event handlers
#         def update_status_before_analysis():
#             return "Starting repository analysis... Please wait."

#         analyze_button.click(update_status_before_analysis, None, analysis_status).then(
#             repo_chat.analyze_repository_with_progress,
#             inputs=[repo_input, github_token, check_plagiarism],
#             outputs=[repo_analysis_output, chatbot],
#         ).then(
#             lambda: "Analysis complete! You can now ask questions about the repository.",
#             None,
#             analysis_status,
#         )

#         # Chat functionality
#         msg_submit = submit_btn.click(
#             repo_chat.chat, inputs=[msg, chatbot], outputs=[chatbot, chat_status]
#         ).then(
#             lambda: "", None, msg  # Clear the message input after sending
#         )

#         # Also trigger on Enter key
#         msg.submit(
#             repo_chat.chat, inputs=[msg, chatbot], outputs=[chatbot, chat_status]
#         ).then(
#             lambda: "", None, msg  # Clear the message input after sending
#         )

#         # Clear chat history
#         def clear_chat():
#             repo_chat.chat_history = []
#             return [], "Chat cleared. Ready for new questions."

#         clear_btn.click(clear_chat, None, [chatbot, chat_status])

#         # Export conversation
#         export_btn.click(repo_chat.get_full_conversation, None, conversation_output)

#         # Reset chat history when analyzing a new repo
#         def clear_history():
#             repo_chat.chat_history = []
#             return [], "Repository loaded. Ready for your questions."

#         analyze_button.click(clear_history, None, [chatbot, chat_status])

#     # Launch with share=True for a public URL if needed
#     demo.launch(share=False, server_name="0.0.0.0", server_port=8080)


# if __name__ == "__main__":
#     launch_app()

# app/gradio_interface.py
import gradio as gr
import requests
import json
import time
import threading
import asyncio
import re
import os
from app.analyzer import analyze_repo, analyze_code_quality

# from app.visualizer import analyze_code_quality,
from app.plagiarism_detector import PlagiarismDetector
from app.utils import load_env

# Load environment variables
load_env()


class RepoChat:
    def __init__(self):
        self.repo_analysis = None
        self.chat_history = []
        self.is_analyzing = False
        self.plagiarism_results = None
        self.file_contents = None
        self.dependency_data = None

    def analyze_repository_with_progress(
        self,
        repo_url,
        github_token=None,
        check_plagiarism=False,
        analyze_code=True,
        file_limit=50,
        progress=gr.Progress(),
    ):
        """Analyze the repository with progress tracking"""
        self.is_analyzing = True
        progress(0, desc="Starting repository analysis...")

        try:
            # Track the start time
            start_time = time.time()

            # Simulate progress updates during analysis
            # Since analyze_repo doesn't provide progress updates, we'll simulate them
            def update_progress():
                steps = 5
                for i in range(1, steps + 1):
                    if not self.is_analyzing:
                        break
                    time.sleep(0.5)  # Delay between updates
                    progress(i / steps, desc=f"Analyzing repository: Phase {i}/{steps}")

            # Start progress updates in a separate thread
            progress_thread = threading.Thread(target=update_progress)
            progress_thread.start()

            # Actually analyze the repository, passing the GitHub token if provided
            try:
                self.repo_analysis = analyze_repo(
                    repo_url,
                    github_token=github_token if github_token else None,
                    file_limit=file_limit,
                )

                # Store file contents for use in queries
                self.file_contents = self.repo_analysis.get("file_contents", {})

                # Get code quality metrics if requested
                if analyze_code and self.file_contents:
                    progress(0.7, desc="Analyzing code quality...")
                    self.code_quality = analyze_code_quality(self.file_contents)
                else:
                    self.code_quality = None

            except Exception as e:
                if "rate limit exceeded" in str(e).lower():
                    raise Exception(
                        f"GitHub API rate limit exceeded. Please provide a GitHub token or try again later. Error: {str(e)}"
                    )
                else:
                    raise e

            # Check for plagiarism if requested
            if check_plagiarism:
                progress(0.8, desc="Checking for potential plagiarism...")
                plagiarism_detector = PlagiarismDetector(github_token=github_token)
                self.plagiarism_results = plagiarism_detector.detect_plagiarism(
                    repo_url
                )
            else:
                self.plagiarism_results = None

            # Stop the progress updates
            self.is_analyzing = False
            progress_thread.join()

            # Calculate time taken
            elapsed_time = time.time() - start_time

            # Get the analysis results
            folder_structure = self.repo_analysis["folder_structure"]
            frameworks = self.repo_analysis["frameworks"]
            additional_info = self.repo_analysis.get("additional_info", "")

            # Count analyzed files
            analyzed_files_count = len(self.file_contents) if self.file_contents else 0

            # Format the repository analysis as markdown for better display
            analysis_markdown = f"""
## Repository Analysis Results
*Analysis completed in {elapsed_time:.2f} seconds*

### Folder Structure
```
{folder_structure}
```

### Files Analyzed
- Total files analyzed: {analyzed_files_count}
"""

            # Add frameworks section if available
            if frameworks:
                analysis_markdown += f"""
### Detected Frameworks/Technologies
{', '.join(frameworks)}
"""

            # Add code quality information if available
            if self.code_quality:
                analysis_markdown += f"""
### Code Quality Metrics
- Total lines of code: {self.code_quality['total_lines']}
- Blank lines: {self.code_quality['blank_lines']}
- Large files (>500 lines): {len(self.code_quality['large_files'])}
- Complex functions: {len(self.code_quality['complex_functions'])}
"""

                if self.code_quality["large_files"]:
                    analysis_markdown += "\n#### Large Files\n"
                    for file in self.code_quality["large_files"][
                        :5
                    ]:  # Show up to 5 large files
                        analysis_markdown += (
                            f"- {file['path']} ({file['lines']} lines)\n"
                        )

                    if len(self.code_quality["large_files"]) > 5:
                        analysis_markdown += f"- ... and {len(self.code_quality['large_files']) - 5} more\n"

            # Add plagiarism information if available
            if self.plagiarism_results:
                analysis_markdown += f"""
### Plagiarism Check Results
{self.plagiarism_results['summary']}

"""
                if self.plagiarism_results["plagiarism_detected"]:
                    analysis_markdown += "#### Suspicious Files:\n"
                    for file in self.plagiarism_results["suspicious_files"]:
                        analysis_markdown += f"- **{file['file']}** - {file['match_type']} (Confidence: {int(file['confidence']*100)}%)\n"
                        analysis_markdown += (
                            f"  - Potential source: {file['potential_source']}\n"
                        )

            # Add additional repository information
            repo_info = additional_info
            if isinstance(repo_info, dict):
                analysis_markdown += f"""
### Repository Information
- Description: {repo_info.get('description', 'Not provided')}
- Primary language: {repo_info.get('language', 'Not detected')}
- Stars: {repo_info.get('stars', 0)}
- Forks: {repo_info.get('forks', 0)}
- Open issues: {repo_info.get('open_issues', 0)}
- Last updated: {repo_info.get('last_update', 'Unknown')}
"""

            # Store frameworks and additional info for chat suggestions
            self.frameworks_info = frameworks
            self.additional_info = additional_info

            # Reset chat history with the system message and initial suggestions
            self.chat_history = []

            # Create initial suggestions message
            suggestions = "**Repository Analysis Complete!** Here are some questions you might want to ask:\n\n"

            if frameworks:
                suggestions += (
                    "- What frameworks/technologies are used in this repository?\n"
                )
                suggestions += "- Can you explain the purpose of the main frameworks?\n"

            suggestions += "- What is the main purpose of this repository?\n"
            suggestions += "- Can you explain the overall architecture?\n"

            if self.file_contents:
                suggestions += (
                    "- Can you explain how the code in [specific file] works?\n"
                )
                suggestions += (
                    "- What are the key functions/classes in this codebase?\n"
                )

            if self.code_quality and self.code_quality["complex_functions"]:
                suggestions += (
                    "- Can you help me understand the complex functions in the code?\n"
                )

            if self.code_quality and self.code_quality["potential_issues"]:
                suggestions += (
                    "- Are there any potential security issues in the code?\n"
                )

            suggestions += "- Are there any security concerns in this codebase?\n"

            if (
                self.plagiarism_results
                and self.plagiarism_results["plagiarism_detected"]
            ):
                suggestions += (
                    "- Can you explain more about the potentially plagiarized code?\n"
                )

            suggestions += "- How can I contribute to this project?\n"

            # Return both the analysis markdown and the suggestions for the chatbot in tuple format
            return analysis_markdown, [(None, suggestions)]

        except Exception as e:
            error_message = f"Error analyzing repository: {str(e)}"
            self.chat_history = []
            self.is_analyzing = False
            if "progress_thread" in locals() and progress_thread.is_alive():
                progress_thread.join()
            progress(1.0, desc="Analysis failed!")
            return error_message, [
                (None, "Error analyzing repository. Please try again.")
            ]

    def query_claude(self, user_message, progress=gr.Progress(), status_updates=None):
        """Send a query to Claude API with the repository context and chat history"""
        if not self.repo_analysis:
            return "Please analyze a repository first."

        # Use the status updates if provided, otherwise use the progress bar
        if status_updates:
            current_status = status_updates[0]
        else:
            progress(0.1, desc="Preparing request...")
            current_status = "Preparing request..."

        # For debugging - print API information instead of showing to user
        print(f"Starting Claude API request for message: {user_message[:50]}...")

        # Get API key from environment variables
        api_key = load_env().get("API_KEY")

        if not api_key:
            return "Error: API_KEY not found in environment variables"

        # Create system message with repository context
        system_message = (
            f"You are assisting with a GitHub repository analysis. Here is the information about the repository:\n\n"
            f"Folder Structure:\n{self.repo_analysis['folder_structure']}\n\n"
            f"Frameworks:\n{self.repo_analysis['frameworks']}\n\n"
            f"Additional Analysis:\n{self.repo_analysis.get('additional_info', '')}\n\n"
        )

        # Add code quality information if available
        if hasattr(self, "code_quality") and self.code_quality:
            system_message += "Code Quality Metrics:\n"
            system_message += (
                f"- Total lines of code: {self.code_quality['total_lines']}\n"
            )
            system_message += f"- Blank lines: {self.code_quality['blank_lines']}\n"

            if self.code_quality["large_files"]:
                system_message += (
                    f"- Large files: {len(self.code_quality['large_files'])}\n"
                )
                for file in self.code_quality["large_files"][:5]:  # Show top 5
                    system_message += f"  - {file['path']} ({file['lines']} lines)\n"

            if self.code_quality["complex_functions"]:
                system_message += f"- Complex functions: {len(self.code_quality['complex_functions'])}\n"
                for func in self.code_quality["complex_functions"][:5]:  # Show top 5
                    system_message += f"  - {func['file']}: {func['function']} ({func['lines']} lines)\n"

            if self.code_quality["potential_issues"]:
                system_message += f"- Potential issues: {len(self.code_quality['potential_issues'])}\n"
                for issue in self.code_quality["potential_issues"][:5]:  # Show top 5
                    system_message += (
                        f"  - {issue['file']} line {issue['line']}: {issue['issue']}\n"
                    )

        # Add dependency information if available
        if hasattr(self, "dependency_data") and self.dependency_data:
            system_message += "\nCode Dependency Analysis:\n"

            metrics = self.dependency_data.get("metrics", {})
            key_files = self.dependency_data.get("key_files", [])[:3]

            system_message += f"- Key files: {', '.join([f[0] for f in key_files])}\n"
            system_message += f"- Entry points: {', '.join(self.dependency_data.get('entry_points', [])[:3])}\n"
            system_message += f"- Average dependencies per file: {metrics.get('avg_dependencies', 0):.2f}\n"

        # Add file contents information
        if self.file_contents:
            system_message += f"\nFile Contents:\n"
            system_message += f"I have access to the contents of {len(self.file_contents)} files from this repository.\n"
            system_message += "If the user asks about specific files or code implementation, I should provide detailed explanations based on these file contents.\n\n"

            # Provide a list of files that have been analyzed
            system_message += "Files available for detailed analysis:\n"
            file_list = list(self.file_contents.keys())
            for file_path in file_list[
                :20
            ]:  # List up to 20 files to avoid token limits
                system_message += f"- {file_path}\n"
            if len(file_list) > 20:
                system_message += f"- ... and {len(file_list) - 20} more files\n"

            # Add important context: when user asks about a specific file, provide its content
            system_message += "\nIf the user asks about a specific file, find its content in the file_contents dictionary and explain the code in detail."

        # Add plagiarism information if available
        if self.plagiarism_results:
            system_message += (
                f"Plagiarism Check Results:\n{self.plagiarism_results['summary']}\n\n"
            )
            if self.plagiarism_results["plagiarism_detected"]:
                system_message += "Suspicious Files:\n"
                for file in self.plagiarism_results["suspicious_files"]:
                    system_message += (
                        f"- {file['file']} - {file['match_type']} (Confidence: {int(file['confidence']*100)}%)\n"
                        f"  Potential source: {file['potential_source']}\n"
                        f"  Snippet: {file['snippet']}\n\n"
                    )

        # If the user asks about a specific file, include the file's content in the system message
        # Check if the user is asking about a specific file
        file_pattern = r"(?:explain|tell me about|analyze|what does|how does|show me|look at).*?(`|\'|\")([^`\'\"]+\.[a-zA-Z0-9]+)(`|\'|\")"
        file_mentions = re.findall(file_pattern, user_message, re.IGNORECASE)

        # Alternative pattern to catch more file references
        alt_pattern = r"(?:file|code in|implementation of|content of).*?(`|\'|\")([^`\'\"]+\.[a-zA-Z0-9]+)(`|\'|\")"
        file_mentions.extend(re.findall(alt_pattern, user_message, re.IGNORECASE))

        # Also check for direct file paths without quotes but with extensions
        direct_pattern = r"\b([a-zA-Z0-9_\-\/\.]+\.(py|js|java|html|css|jsx|tsx|cpp|c|h|cs|go|rb|php|ts))\b"
        direct_matches = re.findall(direct_pattern, user_message, re.IGNORECASE)
        if direct_matches:
            file_mentions.extend([('"', match[0], '"') for match in direct_matches])

        # If files are mentioned, try to find them in our file_contents
        if file_mentions and self.file_contents:
            for _, file_path, _ in file_mentions:
                # Try exact match first
                if file_path in self.file_contents:
                    file_content = self.file_contents[file_path]
                    system_message += f"\n\nContent of file '{file_path}':\n```\n{file_content[:7000]}{'...' if len(file_content) > 7000 else ''}\n```\n"
                else:
                    # Try partial match
                    matching_files = [
                        f for f in self.file_contents.keys() if file_path in f
                    ]
                    if matching_files:
                        best_match = matching_files[0]
                        file_content = self.file_contents[best_match]
                        system_message += f"\n\nContent of file '{best_match}' (matching '{file_path}'):\n```\n{file_content[:7000]}{'...' if len(file_content) > 7000 else ''}\n```\n"

        system_message += (
            f"While you have all this information, the user only sees the folder structure, a summary of code metrics, and plagiarism results if performed. "
            f"If they ask about frameworks or technologies, explain them based on the frameworks information I've provided to you. "
            f"If they ask about specific files or code, use the file contents I've provided to give detailed explanations. "
            f"Analyze the code logic and structure to provide meaningful insights about implementation details, architecture, and design patterns. "
            f"If asked about a specific function or feature, find relevant code in the file contents and explain how it works. "
            f"Similarly, use the additional analysis information when relevant, but don't directly mention that you were given this data separately. "
            f"If they ask about plagiarism, provide insights based on the plagiarism check results if available."
        )

        # Prepare messages for Claude API (without the system role)
        messages = []

        # Add chat history to the messages (limit to last 10 exchanges to avoid token limits)
        for human_msg, ai_msg in self.chat_history[-10:]:
            if human_msg is not None:  # Skip system messages
                messages.append({"role": "user", "content": human_msg})
                messages.append({"role": "assistant", "content": ai_msg})

        # Add the current user message
        messages.append({"role": "user", "content": user_message})

        # Prepare the payload for Claude API - correcting payload format
        payload = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 1000,
            "system": system_message,  # Use top-level system parameter instead of in messages
            "messages": messages,
            "temperature": 0.7,
        }

        # Set headers with API key - using correct header format
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # For debugging - print the request payload instead of showing to user
        print(
            "Sending request to Claude API with payload:", json.dumps(payload, indent=2)
        )

        if status_updates and len(status_updates) > 2:
            current_status = status_updates[2]
        else:
            progress(0.5, desc="Sending request to Claude API...")
            current_status = "Sending request to Claude API..."

        # Send the request to the Claude API
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages", json=payload, headers=headers
            )

            # For debugging - print response status and headers instead of showing to user
            print(f"Response status: {response.status_code}")
            print(
                f"Response: {response.text[:1000]}"
            )  # Print first 1000 chars of response

            response.raise_for_status()

            if not status_updates:
                progress(0.8, desc="Processing response...")

            # Extract the response content
            result = response.json()
            if "content" in result and len(result["content"]) > 0:
                claude_response = result["content"][0]["text"]

                # Update chat history
                self.chat_history.append((user_message, claude_response))

                if not status_updates:
                    progress(1.0, desc="Response ready!")
                return claude_response
            else:
                if not status_updates:
                    progress(1.0, desc="No response content!")
                return "No response content from Claude."

        except requests.exceptions.RequestException as e:
            if not status_updates:
                progress(1.0, desc="Error!")
            error_details = (
                response.text if "response" in locals() else "No response details"
            )
            print(f"API Error details: {error_details}")
            return f"Error querying Claude API: {str(e)}\n\nDetails: {error_details}"

    def chat(self, user_message, history, progress=gr.Progress()):
        """Process a chat message and update the history"""
        if not user_message.strip():
            return history, "Please enter a question."

        # Return status updates to the dedicated status area instead of using progress popup
        status_updates = [
            "Processing your question...",
            "Sending request to Claude API...",
            "Waiting for response...",
        ]

        # Use the first status update instead of progress popup
        # progress(0.1, desc=status_updates[0])
        response = self.query_claude(
            user_message, progress, status_updates=status_updates
        )

        # Ensure we're using the tuple format that matches the chatbot type
        history.append((user_message, response))

        # Also update the internal chat history for the API
        self.chat_history.append((user_message, response))

        # Return ready status after completion
        return history, "Ready to answer more questions."

    def get_full_conversation(self):
        """Return the full conversation history in a copyable format"""
        if not self.chat_history:
            return "No conversation history available."

        conversation = []
        for user_msg, claude_msg in self.chat_history:
            conversation.append(f"User: {user_msg}")
            conversation.append(f"Claude: {claude_msg}")
            conversation.append("---")

        return "\n\n".join(conversation)

    def analyze_dependencies(self, progress=gr.Progress()):
        """Analyze code dependencies between files"""
        if (
            not self.repo_analysis
            or not hasattr(self, "file_contents")
            or not self.file_contents
        ):
            return "Please analyze a repository first."

        try:
            progress(0.3, desc="Analyzing code dependencies...")

            # Import dependency analyzer
            from app.dependency_analyzer import DependencyAnalyzer

            analyzer = DependencyAnalyzer()

            # Analyze dependencies
            dependency_data = analyzer.analyze_dependencies(self.file_contents)
            self.dependency_data = dependency_data

            progress(0.7, desc="Generating visualization...")

            # Generate visualization
            from app.visualizer import (
                generate_dependency_graph,
                generate_dependency_summary,
            )

            # Generate summary
            summary = generate_dependency_summary(dependency_data)

            # Generate graph
            try:
                graph_data = generate_dependency_graph(dependency_data)
                graph_html = f'<img src="{graph_data}" alt="Dependency Graph" style="max-width:100%;">'

                # Combine summary and graph
                result = f"{summary}\n\n### Dependency Graph\n{graph_html}"
            except Exception as e:
                print(f"Error generating graph: {str(e)}")
                result = f"{summary}\n\n### Dependency Graph\nError generating graph: {str(e)}"

            progress(1.0, desc="Dependency analysis complete!")
            return result

        except Exception as e:
            progress(1.0, desc="Analysis failed!")
            return f"Error analyzing dependencies: {str(e)}"


def launch_app(share=False):
    repo_chat = RepoChat()

    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# GitLens - Github Repo Chat Assistant with Code Understanding")

        with gr.Row():
            with gr.Column(scale=3):
                repo_input = gr.Textbox(
                    label="Enter GitHub Repository URL",
                    placeholder="https://github.com/username/repository",
                )
            with gr.Column(scale=2):
                github_token = gr.Textbox(
                    label="GitHub Token (Optional)",
                    placeholder="ghp_xxxxxxxxxxxx",
                    type="password",
                    info="Avoids rate limiting. Create one at github.com/settings/tokens",
                )
            with gr.Column(scale=1):
                analyze_button = gr.Button("Analyze Repository", variant="primary")

        # Options for analysis
        with gr.Row():
            with gr.Column(scale=1):
                check_plagiarism = gr.Checkbox(
                    label="Check for potential plagiarism", value=False
                )
            with gr.Column(scale=1):
                analyze_code = gr.Checkbox(label="Analyze code quality", value=True)
            with gr.Column(scale=1):
                file_limit = gr.Slider(
                    minimum=10,
                    maximum=200,
                    value=50,
                    step=10,
                    label="Maximum files to analyze",
                )

        # Analysis status indicator
        analysis_status = gr.Markdown(
            "Enter a repository URL and click 'Analyze Repository' to begin."
        )

        # Repository analysis section with copy button
        with gr.Accordion("Repository Analysis", open=True):
            repo_analysis_output = gr.Markdown(label="Analysis Results")

        # Dependency analysis section
        with gr.Accordion("Code Dependency Analysis", open=False):
            with gr.Row():
                dependency_btn = gr.Button("Analyze Code Dependencies", variant="secondary")
                dependency_status = gr.Markdown("Click the button to analyze code dependencies")
            dependency_output = gr.HTML(label="Dependency Analysis")

        # Chatbot interface with consistent type
        with gr.Accordion("Chat with Repository Assistant", open=True):
            # Add a dedicated status area above the chatbot
            chat_status = gr.Markdown("Ready to answer questions about the repository.")

            chatbot = gr.Chatbot(
                label="Chat with Claude about this repository",
                height=400,
                show_copy_button=True,
                type="tuples",  # Keep using tuples to avoid format mismatch issues
            )

            with gr.Row():
                with gr.Column(scale=4):
                    msg = gr.Textbox(
                        label="Ask about the repository",
                        placeholder="What is the main purpose of this repository?",
                        lines=2,
                    )
                with gr.Column(scale=1):
                    submit_btn = gr.Button("Send", variant="primary")

        # Add a file explorer to browse repository files
        with gr.Accordion("Repository Files", open=False):
            file_explorer = gr.Dataframe(
                headers=["File", "Type", "Size", "Last Modified"],
                datatype=["str", "str", "str", "str"],
                row_count=10,
                col_count=(4, "fixed"),
                interactive=False,
            )
            view_file_btn = gr.Button("View Selected File")
            file_content_display = gr.Code(
                label="File Content", language="python", interactive=False, lines=25
            )

        # Add buttons for chat management
        with gr.Row():
            clear_btn = gr.Button("Clear Chat")
            export_btn = gr.Button("Export Conversation")

        # Export conversation output
        with gr.Accordion("Conversation Export", open=False):
            conversation_output = gr.TextArea(
                label="Full Conversation",
                lines=10,
                placeholder="Your conversation will appear here after clicking 'Export Conversation'",
                interactive=False,
            )
            copy_btn = gr.Button("Copy to Clipboard")

        # Set up event handlers
        def update_status_before_analysis():
            return "Starting repository analysis... Please wait."

        analyze_button.click(update_status_before_analysis, None, analysis_status).then(
            repo_chat.analyze_repository_with_progress,
            inputs=[
                repo_input,
                github_token,
                check_plagiarism,
                analyze_code,
                file_limit,
            ],
            outputs=[repo_analysis_output, chatbot],
        ).then(
            lambda: "Analysis complete! You can now ask questions about the repository.",
            None,
            analysis_status,
        )

        # Dependency analysis handler with loading status
        def update_status_before_dependency_analysis():
            return "⏳ Analyzing dependencies... This may take a minute for larger repositories."
        
        # This function isn't needed since we handle it elsewhere
        # Keeping the function signature for reference
        def update_status_after_dependency_analysis(result):
            return "✅ Dependency analysis complete!"
            
        # Use separate functions with proper return values for gradio
        def analyze_with_error_handling(progress=gr.Progress()):
            try:
                progress(0.1, desc="Starting dependency analysis...")
                result = repo_chat.analyze_dependencies(progress)
                return "✅ Dependency analysis complete!", result
            except Exception as e:
                error_msg = str(e)
                return f"❌ Error: {error_msg}", f"<div style='color: red; padding: 10px; border: 1px solid red; border-radius: 5px;'>Analysis failed: {error_msg}</div>"
        
        dependency_btn.click(
            lambda: "⏳ Analyzing dependencies... This may take a minute for larger repositories.",
            None,
            dependency_status
        ).then(
            analyze_with_error_handling,
            None, 
            [dependency_status, dependency_output]
        )

        # Chat functionality
        msg_submit = submit_btn.click(
            repo_chat.chat, inputs=[msg, chatbot], outputs=[chatbot, chat_status]
        ).then(
            lambda: "", None, msg  # Clear the message input after sending
        )

        # Also trigger on Enter key
        msg.submit(
            repo_chat.chat, inputs=[msg, chatbot], outputs=[chatbot, chat_status]
        ).then(
            lambda: "", None, msg  # Clear the message input after sending
        )

        # Clear chat history
        def clear_chat():
            repo_chat.chat_history = []
            return [], "Chat cleared. Ready for new questions."

        clear_btn.click(clear_chat, None, [chatbot, chat_status])

        # Export conversation
        export_btn.click(repo_chat.get_full_conversation, None, conversation_output)

        # Reset chat history when analyzing a new repo
        def clear_history():
            repo_chat.chat_history = []
            return [], "Repository loaded. Ready for your questions."

        analyze_button.click(clear_history, None, [chatbot, chat_status])

        # File explorer functionality
        def update_file_explorer():
            if (
                not repo_chat.repo_analysis
                or not hasattr(repo_chat, "file_contents")
                or not repo_chat.file_contents
            ):
                return [], "No files available. Please analyze a repository first."

            file_metadata = repo_chat.repo_analysis.get("file_metadata", {})
            files_data = []

            for file_path, metadata in file_metadata.items():
                if not metadata.get(
                    "skipped", True
                ):  # Only show files that were actually analyzed
                    files_data.append(
                        [
                            file_path,
                            metadata.get("type", "unknown"),
                            f"{metadata.get('size', 0):,} bytes",
                            metadata.get("last_modified", "unknown"),
                        ]
                    )

            return files_data, "Select a file to view its contents."

        # Function to view selected file content
        def view_file_content(selected_data, files_data):
            if not selected_data or len(selected_data) == 0:
                return "No file selected"  # Only return the content

            # Get the first selected row (file path is in the first column)
            selected_file_path = (
                selected_data[0][0]
                if isinstance(selected_data[0], list)
                else selected_data[0]
            )

            # Rest of your function remains the same
            file_ext = os.path.splitext(selected_file_path)[1].lower()

            # Map file extensions to language for syntax highlighting
            language_map = {
                ".py": "python",
                ".js": "javascript",
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".html": "html",
                ".css": "css",
                ".java": "java",
                ".c": "c",
                ".cpp": "cpp",
                ".h": "c",
                ".cs": "csharp",
                ".go": "go",
                ".rb": "ruby",
                ".php": "php",
                ".json": "json",
                ".md": "markdown",
                ".yml": "yaml",
                ".yaml": "yaml",
                ".sh": "bash",
                ".sql": "sql",
            }

            language = language_map.get(file_ext, "text")

            # Get file content
            if selected_file_path in repo_chat.file_contents:
                content = repo_chat.file_contents[selected_file_path]
                # Instead of returning language separately, configure the Code component directly
                file_content_display.language = (
                    language  # This sets the language property
                )
                return content
            else:
                file_content_display.language = "text"
                return f"Content not available for {selected_file_path}"
            # Update file explorer when repository is analyzed

        analyze_button.click(lambda: [], None, file_explorer).then(
            update_file_explorer, None, [file_explorer, chat_status]
        )

        # View file content when a file is selected
        view_file_btn.click(
            view_file_content,
            inputs=[file_explorer, file_explorer],
            outputs=file_content_display,
        )

        # Copy to clipboard functionality
        copy_btn.click(
            lambda text: None,
            inputs=[conversation_output],
            js="text => navigator.clipboard.writeText(text)",
        )

    # Launch with share=True for a public URL if needed
    demo.launch(share=share)


if __name__ == "__main__":
    launch_app()
