from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import subprocess
import os
import psutil
from threading import Lock
from sqlalchemy.orm import Session
from models import Task as TaskModel
from database import get_db

router = APIRouter()

class TaskCommand(BaseModel):
    task_id: str
    command: List[str]
    log_path: str

class TaskManager:
    def __init__(self):
        self.active_tasks: Dict[str, subprocess.Popen] = {}
        self.lock = Lock()

    def reconstruct_from_db(self, db: Session):
        running_tasks = db.query(TaskModel).filter(TaskModel.status == "running").all()
        for task in running_tasks:
            if task.pid and psutil.pid_exists(task.pid):
                try:
                    proc = psutil.Process(task.pid)
                    if proc.status() in (psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING):
                        self.active_tasks[task.task_id] = proc
                    else:
                        task.status = "error"
                        db.commit()
                except Exception:
                    task.status = "error"
                    db.commit()
            else:
                task.status = "error"
                db.commit()

    def start_task(self, task_id: str, command: List[str], log_path: str, db: Session):
        with self.lock:
            if task_id in self.active_tasks:
                raise ValueError("Task is already running")

            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            log_file = open(log_path, "w")
            proc = subprocess.Popen(command, stdout=log_file, stderr=subprocess.STDOUT)
            self.active_tasks[task_id] = proc

            # Update DB status
            task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
            if task:
                task.status = "running"
                task.pid = proc.pid
                db.commit()

            return proc.pid

    def cancel_task(self, task_id: str, db: Session):
        with self.lock:
            proc = self.active_tasks.get(task_id)
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait()
                del self.active_tasks[task_id]

                task = db.query(TaskModel).filter(TaskModel.task_id == task_id).first()
                if task:
                    task.status = "cancelled"
                    db.commit()
                return True
            return False

    def restart_task(self, task_id: str, command: List[str], log_path: str, db: Session):
        self.cancel_task(task_id, db)
        return self.start_task(task_id, command, log_path, db)

    def task_status(self, task_id: str):
        proc = self.active_tasks.get(task_id)
        if not proc:
            return "not_found"
        return "running" if proc.poll() is None else "completed"


# Singleton instance
task_manager = TaskManager()

@router.on_event("startup")
def on_startup():
    db = next(get_db())
    task_manager.reconstruct_from_db(db)

@router.post("/tasks/run")
def run_task(task: TaskCommand, db: Session = get_db()):
    try:
        pid = task_manager.start_task(task.task_id, task.command, task.log_path, db)
        return {"status": "started", "pid": pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = get_db()):
    result = task_manager.cancel_task(task_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Task not running or not found")
    return {"status": "cancelled"}

@router.post("/tasks/{task_id}/restart")
def restart_task(task_id: str, task: TaskCommand, db: Session = get_db()):
    pid = task_manager.restart_task(task_id, task.command, task.log_path, db)
    return {"status": "restarted", "pid": pid}

@router.get("/tasks/{task_id}/status")
def get_status(task_id: str):
    status = task_manager.task_status(task_id)
    return {"task_id": task_id, "status": status}
