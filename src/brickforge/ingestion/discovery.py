import os
import stat
from datetime import datetime

def walk_registered_roots(roots):
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.isfile(file_path):
                    yield {
                        'relative_path': os.path.relpath(file_path, root),
                        'language_hint': get_language_hint(filename),
                        'file_size': os.path.getsize(file_path),
                        'modification_time': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    }

def get_language_hint(filename):
    # Simple heuristic to determine file language based on extension
    extension = os.path.splitext(filename)[1].lower()
    if extension in ['.py', '.pyi']:
        return 'python'
    elif extension in ['.js', '.jsx']:
        return 'javascript'
    elif extension in ['.java']:
        return 'java'
    elif extension in ['.go']:
        return 'go'
    elif extension in ['.c', '.h']:
        return 'c'
    elif extension in ['.cpp', '.hpp']:
        return 'cpp'
    elif extension in ['.rb']:
        return 'ruby'
    elif extension in ['.php']:
        return 'php'
    elif extension in ['.swift']:
        return 'swift'
    elif extension in ['.kts', '.kt']:
        return 'kotlin'
    elif extension in ['.rs']:
        return 'rust'
    elif extension in ['.ts']:
        return 'typescript'
    elif extension in ['.html', '.htm']:
        return 'html'
    elif extension in ['.css']:
        return 'css'
    elif extension in ['.json']:
        return 'json'
    elif extension in ['.xml']:
        return 'xml'
    elif extension in ['.yaml', '.yml']:
        return 'yaml'
    elif extension in ['.md']:
        return 'markdown'
    else:
        return 'unknown'
