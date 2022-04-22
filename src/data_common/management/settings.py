from ruamel import yaml
import os
from pathlib import Path
import json
import toml


def get_settings(toml_file: str = "pyproject.toml", env_file: str = ".env"):
    """
    populate a settings dictionary from 'settings.yaml'
    is "$$ENV$$" is the value, first try and get it from the env
    Then will try directly from the '.env' file.
    """

    top_level = []
    attempt = 0
    while Path(*top_level, toml_file).exists() is False and attempt < 10:
        top_level.append("..")
        attempt += 1
    if Path(*top_level, toml_file).exists() is False:
        return {}

    settings_file = Path(*top_level, toml_file)

    data = toml.load(settings_file)["notebook"]["settings"]

    env_data = {}
    if env_file and Path(*top_level, env_file).exists():
        with open(env_file, "r") as fp:
            env_data = [x.split("=", 1) for x in fp.readlines()]
            env_data = {x: y for x, y in env_data}

    for k, v in data.items():
        if v == "$$ENV$$":
            # try and get from environment
            data[k] = os.environ.get(k, "").strip()
            # if we have the file, prefer this
            if k in env_data:
                data[k] = env_data[k].strip()
        if data[k] and isinstance(data[k], str) and data[k][0] == "{":
            data[k] = json.loads(data[k])

    return data


settings = get_settings()
