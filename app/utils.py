from dotenv import load_dotenv
import os


def load_env():
    load_dotenv()
    return {key: os.getenv(key) for key in ["API_KEY"]}
