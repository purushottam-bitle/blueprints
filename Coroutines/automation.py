from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import requests
import time
import os

# Constants
TEST_BEDS = [
    {"name": "tb1", "ip": "192.168.1.101"},
    {"name": "tb2", "ip": "192.168.1.102"}
]
FASTAPI_PORT = 8000
AUTOMATION = "regression"
SUITE = "login"
LOCAL_REPORT_DIR = "/opt/robot_reports"
MERGED_REPORT = f"{LOCAL_REPORT_DIR}/merged_output.xml"

# Ensure local report dir exists
os.makedirs(LOCAL_REPORT_DIR, exist_ok=True)

def trigger_test_bed(tb):
    url = f"http://{tb['ip']}:{FASTAPI_PORT}/tasks/start"
    payload = {
        "command": f"robot --output {tb['name']}_output.xml tests/{SUITE}",
        "test_bed": tb['name'],
        "automation": AUTOMATION,
        "suite": SUITE
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()["task_id"]

def wait_for_completion(tb, task_id):
    url = f"http://{tb['ip']}:{FASTAPI_PORT}/tasks/status/{task_id}"
    for _ in range(60):  # Poll up to 10 minutes
        time.sleep(10)
        response = requests.get(url)
        status = response.json().get("status")
        if status and "finished" in status:
            return True
    raise TimeoutError(f"Test on {tb['name']} timed out.")

def fetch_report(tb):
    remote_file = f"logs/{tb['name']}_output.xml"
    local_file = f"{LOCAL_REPORT_DIR}/{tb['name']}_output.xml"
    # Replace this with actual SCP or API download logic
    os.system(f"scp user@{tb['ip']}:{remote_file} {local_file}")

def merge_reports():
    files = ' '.join([f"{LOCAL_REPORT_DIR}/{tb['name']}_output.xml" for tb in TEST_BEDS])
    os.system(f"rebot --output {MERGED_REPORT} {files}")

with DAG(
    dag_id="robot_test_merge_dag",
    start_date=days_ago(1),
    schedule_interval=None,
    catchup=False,
    description="Trigger test beds, fetch and merge Robot reports"
) as dag:

    # Step 1: Trigger all test beds
    trigger_tasks = []
    for tb in TEST_BEDS:
        task = PythonOperator(
            task_id=f"trigger_{tb['name']}",
            python_callable=trigger_test_bed,
            op_args=[tb]
        )
        trigger_tasks.append(task)

    # Step 2: Wait for completion
    wait_tasks = []
    for i, tb in enumerate(TEST_BEDS):
        wait_task = PythonOperator(
            task_id=f"wait_{tb['name']}",
            python_callable=wait_for_completion,
            op_args=[tb, f"{{{{ ti.xcom_pull(task_ids='trigger_{tb['name']}') }}}}"]
        )
        trigger_tasks[i] >> wait_task
        wait_tasks.append(wait_task)

    # Step 3: Fetch reports
    fetch_tasks = []
    for tb in TEST_BEDS:
        fetch_task = PythonOperator(
            task_id=f"fetch_report_{tb['name']}",
            python_callable=fetch_report,
            op_args=[tb]
        )
        wait_tasks[TEST_BEDS.index(tb)] >> fetch_task
        fetch_tasks.append(fetch_task)

    # Step 4: Merge reports
    merge_task = PythonOperator(
        task_id="merge_reports",
        python_callable=merge_reports
    )

    for task in fetch_tasks:
        task >> merge_task
