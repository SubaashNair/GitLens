"""
Simplified entry point for Hugging Face Spaces.
This version removes dependency checks and other features that might
cause issues in the HF environment.
"""

import gradio as gr
from app.gradio_interface import launch_app

# Simple wrapper for HF spaces that doesn't include checks
def main():
    """Launch the app with minimal setup for Hugging Face deployment"""
    print("Starting GitLens for Hugging Face Spaces deployment...")
    launch_app(share=False)

# This version will be used by Hugging Face
if __name__ == "__main__":
    main()