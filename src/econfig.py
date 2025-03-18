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

_config = {}
def load_env(file_name: str):
    global _config
    dotenv_config = dotenv.dotenv_values(file_name)
    _config = {
        **dotenv_config,
        **os.environ,
    }


def get(key: str, default:str|None=None, override: str | None=None):
    global _config
    if override is not None:
        return override
    return _config.get(key, default)


def get_int(key: str, default: int | None=None, override: int | None=None) -> int:
    global _config
    if override is not None:
        return override
    value= _config.get(key)
    if value:
        return int(value)
    return default

def get_bool(key: str, default: bool | None=None, override: bool | None=None) -> bool:
    global _config
    if override is not None:
        return override
    value = _config.get(key)
    if value:
        return value.lower() in ['true', 'yes', 'y', 'on', '1']
    return default

