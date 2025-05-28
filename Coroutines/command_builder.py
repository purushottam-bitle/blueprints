# airflow_task_runner.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests

# CONFIGURATION
FASTAPI_BASE_URL = "http://<device_farm_ms>:8000"  # Replace with actual URL

# Default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1)
}

def create_task_in_db(task_id, command, log_path):
    payload = {
        "task_id": task_id,
        "command": command,
        "log_path": log_path
    }
    # Optional: Create task entry in DB via FastAPI
    response = requests.post(f"{FASTAPI_BASE_URL}/tasks/run", json=payload)
    if response.status_code != 200:
        raise Exception(f"Failed to start task: {response.text}")
    return response.json()

def monitor_task_status(task_id):
    import time
    while True:
        status_response = requests.get(f"{FASTAPI_BASE_URL}/tasks/{task_id}/status")
        status = status_response.json().get("status")
        print(f"Task {task_id} status: {status}")
        if status != "running":
            break
        time.sleep(10)

def define_dag_for_robot_task(task_id, command, log_path):
    with DAG(
        dag_id=f"robot_task_{task_id}",
        default_args=default_args,
        description=f"Run Robot automation for task {task_id}",
        schedule_interval=None,
        start_date=datetime(2023, 1, 1),
        catchup=False,
        tags=["robot", "device_farm"]
    ) as dag:

        start_task = PythonOperator(
            task_id="create_and_start_task",
            python_callable=create_task_in_db,
            op_args=[task_id, command, log_path]
        )

        monitor_task = PythonOperator(
            task_id="monitor_task_status",
            python_callable=monitor_task_status,
            op_args=[task_id]
        )

        start_task >> monitor_task

        return dag

# Example: register this DAG in Airflow
example_task_id = "robot_test_case_001"
example_command = ["robot", "--outputdir", "results", "tests/login.robot"]
example_log_path = "C:/device_farm/logs/robot_test_case_001.log"

globals()[f"robot_task_{example_task_id}"] = define_dag_for_robot_task(example_task_id, example_command, example_log_path)


# --- TaskManager class (snippet) ---

from models import Task  # Assume Task is your SQLAlchemy ORM model
from sqlalchemy.orm import Session
import uuid, datetime

class TaskManager:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, command, log_path, test_bed_id=None, metadata=None):
        task_id = str(uuid.uuid4())
        new_task = Task(
            task_id=task_id,
            command=command,
            log_path=log_path,
            status="pending",
            start_time=datetime.datetime.utcnow(),
            test_bed_id=test_bed_id,
            metadata=metadata or {}
        )
        self.db.add(new_task)
        self.db.commit()
        self.db.refresh(new_task)
        return new_task

# --- RobotCommandBuilder Utility ---

class RobotCommandBuilder:
    def __init__(self, suite_path: str, output_dir: str):
        self.suite_path = suite_path
        self.output_dir = output_dir
        self.variables = []
        self.tags = []
        self.test_cases = []

    def add_variable(self, key: str, value: str):
        self.variables.append((key, value))

    def add_tag(self, tag: str):
        self.tags.append(tag)

    def add_test_case(self, test_name: str):
        self.test_cases.append(test_name)

    def build(self):
        cmd = ["robot"]

        for k, v in self.variables:
            cmd.extend(["-v", f"{k}:{v}"])

        for tag in self.tags:
            cmd.extend(["-i", tag])

        for test in self.test_cases:
            cmd.extend(["--test", test])

        cmd.extend(["--outputdir", self.output_dir])
        cmd.append(self.suite_path)

        return cmd

# --- PabotCommandBuilder Utility ---

class PabotCommandBuilder:
    def __init__(self, suite_path: str, output_dir: str, processes: int = 2):
        self.suite_path = suite_path
        self.output_dir = output_dir
        self.processes = processes
        self.variables = []
        self.tags = []
        self.test_cases = []

    def add_variable(self, key: str, value: str):
        self.variables.append((key, value))

    def add_tag(self, tag: str):
        self.tags.append(tag)

    def add_test_case(self, test_name: str):
        self.test_cases.append(test_name)

    def build(self):
        cmd = ["pabot", f"--processes", str(self.processes)]

        for k, v in self.variables:
            cmd.extend(["-v", f"{k}:{v}"])

        for tag in self.tags:
            cmd.extend(["-i", tag])

        for test in self.test_cases:
            cmd.extend(["--test", test])

        cmd.extend(["--outputdir", self.output_dir])
        cmd.append(self.suite_path)

        return cmd
