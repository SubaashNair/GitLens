# from app.gradio_interface import launch_app

# if __name__ == "__main__":
#     launch_app()


from app.gradio_interface import launch_app
import os
import sys


def check_requirements():
    """Check if all required packages are installed"""
    try:
        import gradio
        import requests
        import networkx
        import matplotlib
        import chardet
        from dotenv import load_dotenv

        print("All required packages found.")
        return True
    except ImportError as e:
        print(f"Missing required package: {e}")
        print("Please run: pip install -r requirements.txt")
        return False


def check_api_key():
    """Check if the API key is set in the environment"""
    from app.utils import load_env

    api_key = load_env().get("API_KEY")

    if not api_key:
        print("Warning: API_KEY is not set in the environment.")
        print("Please create a .env file with your API_KEY to use Claude.")
        return False
    return True


def print_banner():
    banner = """                       
                                     
    GitHub Repository Analysis Tool with Code Understanding
    """
    print(banner)
    print("\nStarting GitLens with enhanced code understanding...\n")


if __name__ == "__main__":
    print_banner()

    if check_requirements():
        check_api_key()  # Just warn if not set

        # Parse command line arguments
        share = "--share" in sys.argv
        debug = "--debug" in sys.argv

        if debug:
            print("Debug mode enabled. Detailed logs will be shown.")
            import logging

            logging.basicConfig(level=logging.DEBUG)

        # Launch the app
        print("Launching GitLens interface...")
        launch_app(share=share)
    else:
        print("Exiting due to missing requirements.")
        sys.exit(1)
