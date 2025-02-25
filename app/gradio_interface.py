# mark3 with plagiarism
import gradio as gr
import requests
import json
import time
import threading
import asyncio
from app.plagiarism_detector import PlagiarismDetector
from app.analyzer import analyze_repo
from app.utils import load_env

# Load environment variables
load_env()


class RepoChat:
    def __init__(self):
        self.repo_analysis = None
        self.chat_history = []
        self.is_analyzing = False
        self.plagiarism_results = None

    def analyze_repository_with_progress(
        self,
        repo_url,
        github_token=None,
        check_plagiarism=False,
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
                    repo_url, github_token=github_token if github_token else None
                )
            except Exception as e:
                if "rate limit exceeded" in str(e).lower():
                    raise Exception(
                        f"GitHub API rate limit exceeded. Please provide a GitHub token or try again later. Error: {str(e)}"
                    )
                else:
                    raise e

            # Check for plagiarism if requested
            if check_plagiarism:
                progress(0.6, desc="Checking for potential plagiarism...")
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

            # Format the repository analysis as markdown for better display
            analysis_markdown = f"""
## Repository Analysis Results
*Analysis completed in {elapsed_time:.2f} seconds*

### Folder Structure
```
{folder_structure}
```
"""

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

        system_message += (
            f"While you have all this information, the user only sees the folder structure and a summary of plagiarism results if performed. "
            f"If they ask about frameworks or technologies, explain them based on the frameworks information I've provided to you. "
            f"Similarly, use the additional analysis information when relevant, but don't directly mention that you were given this data separately. "
            f"If they ask about plagiarism, provide insights based on the plagiarism check results if available."
        )

        if status_updates and len(status_updates) > 1:
            current_status = status_updates[1]
        else:
            progress(0.3, desc="Building message context...")
            current_status = "Building message context..."

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


def launch_app():
    repo_chat = RepoChat()

    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# GitLens - Github Repo Chat Assistant")

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
            check_plagiarism = gr.Checkbox(
                label="Check for potential plagiarism", value=False
            )

        # Analysis status indicator
        analysis_status = gr.Markdown(
            "Enter a repository URL and click 'Analyze Repository' to begin."
        )

        # Repository analysis section with copy button
        with gr.Accordion("Repository Analysis", open=True):
            repo_analysis_output = gr.Markdown(label="Analysis Results")

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
            inputs=[repo_input, github_token, check_plagiarism],
            outputs=[repo_analysis_output, chatbot],
        ).then(
            lambda: "Analysis complete! You can now ask questions about the repository.",
            None,
            analysis_status,
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

    # Launch with share=True for a public URL if needed
    demo.launch()


if __name__ == "__main__":
    launch_app(share=True)
