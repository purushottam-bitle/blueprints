# app/task_manager.py
from subprocess import Popen, PIPE
from threading import Lock
import uuid
import os
import sqlite3
import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def create_db():
    with sqlite3.connect("tasks.db") as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            command TEXT,
            status TEXT,
            log_path TEXT,
            test_bed TEXT,
            automation TEXT,
            suite TEXT,
            created_at TEXT
        )''')

create_db()

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.lock = Lock()

    def _log_file_path(self, task_id):
        return os.path.join(LOG_DIR, f"{task_id}.log")

    def start_task(self, command: str, test_bed: str, automation: str, suite: str):
        with self.lock:
            task_id = str(uuid.uuid4())
            log_path = self._log_file_path(task_id)
            with open(log_path, "w") as log_file:
                process = Popen(command, shell=True, stdout=log_file, stderr=log_file, text=True)
            self.tasks[task_id] = {
                "process": process,
                "command": command,
                "log_path": log_path,
                "status": "running",
                "test_bed": test_bed,
                "automation": automation,
                "suite": suite
            }
            self._save_to_db(task_id, command, "running", log_path, test_bed, automation, suite)
            return task_id

    def _save_to_db(self, task_id, command, status, log_path, test_bed, automation, suite):
        with sqlite3.connect("tasks.db") as conn:
            conn.execute("""
                INSERT INTO tasks (task_id, command, status, log_path, test_bed, automation, suite, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_id, command, status, log_path, test_bed, automation, suite, datetime.datetime.utcnow().isoformat()))

    def get_status(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            return self._get_status_from_db(task_id)
        process = task["process"]
        if process.poll() is None:
            return "running"
        else:
            return f"finished (code={process.returncode})"

    def cancel_task(self, task_id):
        task = self.tasks.get(task_id)
        if task and task["process"].poll() is None:
            task["process"].terminate()
            task["status"] = "terminated"
            self._update_status(task_id, "terminated")
            return True
        return False

    def restart_task(self, task_id):
        task = self.tasks.get(task_id)
        if not task:
            task = self._get_task_from_db(task_id)
            if not task:
                return None
        return self.start_task(task["command"], task.get("test_bed", ""), task.get("automation", ""), task.get("suite", ""))

    def _update_status(self, task_id, status):
        with sqlite3.connect("tasks.db") as conn:
            conn.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task_id))

    def _get_task_from_db(self, task_id):
        with sqlite3.connect("tasks.db") as conn:
            cursor = conn.execute("SELECT command, test_bed, automation, suite FROM tasks WHERE task_id=?", (task_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "command": row[0],
                    "test_bed": row[1],
                    "automation": row[2],
                    "suite": row[3]
                }
            return None

    def _get_status_from_db(self, task_id):
        with sqlite3.connect("tasks.db") as conn:
            cursor = conn.execute("SELECT status FROM tasks WHERE task_id=?", (task_id,))
            row = cursor.fetchone()
            return row[0] if row else "not found"

    def get_log(self, task_id):
        log_path = self._log_file_path(task_id)
        if not os.path.exists(log_path):
            return "Log not found"
        with open(log_path, "r") as file:
            return file.read()

task_manager = TaskManager()
