import os
from typing import List
import fnmatch

class IgnoreRules:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.ignore_patterns = self.load_ignore_patterns()

    def load_ignore_patterns(self) -> List[str]:
        ignore_patterns = []
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as file:
                for line in file:
                    pattern = line.strip()
                    if pattern and not pattern.startswith('#'):
                        ignore_patterns.append(pattern)
        return ignore_patterns

    def is_ignored(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
