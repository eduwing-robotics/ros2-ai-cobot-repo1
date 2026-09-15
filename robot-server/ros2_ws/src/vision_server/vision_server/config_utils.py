from pathlib import Path

import yaml
from ament_index_python.packages import get_package_share_directory


def default_path(relative_path: str) -> str:
    share = Path(get_package_share_directory('vision_server'))
    return str(share / relative_path)


def load_yaml(path: str) -> dict:
    with Path(path).expanduser().open('r', encoding='utf-8') as stream:
        data = yaml.safe_load(stream)
    return data or {}


def resolve_package_path(path: str) -> str:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str(Path(get_package_share_directory('vision_server')) / candidate)
