'''
Manage configuration from the environment or a env fil.
'''
import os
import dotenv

DATABASE_URL="DATABASE_URL"

BROWSER="BROWSER"
FIREFOX_PATH="FIREFOX_PATH"
HEADLESS="HEADLESS"

MTN_WEB_URL="MTN_WEB_URL"
MTN_WEB_USERNAME="MTN_WEB_USERNAME"
MTN_WEB_PASSWORD="MTN_WEB_PASSWORD"

def load_env():
    dotenv.load_dotenv()


def get(key: str, default:str|None=None, override: str | None=None) -> str | None:
    if override is not None:
        return override
    return os.environ.get(key, default)


def get_int(key: str, default: int | None=None, override: int | None=None) -> int:
    if override is not None:
        return override
    try:
        value = os.environ[key]
        result = int(value)
    except KeyError:
        result = default
    return result

def get_bool(key: str, default: bool | None=None, override: bool | None=None) -> bool:
    if override is not None:
        return override
    try:
        value = os.environ[key]
        result = value.lower() in ['true', 'yes', 'y', 'on', '1']
    except KeyError:
        result = default
    return result

