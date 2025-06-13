from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.utils.context import Context
import sys
import os
import requests
import shutil

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from update_job_status import update_job_status

def get_job_id_from_context(context: Context):
    return int(context['dag_run'].conf.get('job_id'))

def allocate_tasks(job_id: int):
    task_manager_url = f"http://taskmanager.local/api/jobs/{job_id}/allocate"
    response = requests.post(task_manager_url)
    if response.status_code != 200:
        raise Exception(f"Failed to allocate tasks for job {job_id}: {response.text}")
    print(f"Tasks allocated for job {job_id}: {response.json()}")

def wait_for_all_tasks(job_id: int, poll_interval: int = 10, timeout: int = 600):
    import time
    task_manager_status_url = f"http://taskmanager.local/api/jobs/{job_id}/status"
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(task_manager_status_url)
        if response.status_code != 200:
            raise Exception(f"Failed to get task status for job {job_id}: {response.text}")
        status = response.json().get("status")
        print(f"Polled status: {status}")
        if status == "completed":
            print(f"All tasks completed for job {job_id}")
            return True
        time.sleep(poll_interval)
    raise Exception(f"Timeout reached while waiting for tasks of job {job_id} to complete")

def merge_xml_reports(job_id: int):
    report_dir = f"/path/to/reports/{job_id}"
    remote_nodes = ["node1.local", "node2.local"]  # Add more nodes as needed
    os.makedirs(report_dir, exist_ok=True)

    for node in remote_nodes:
        node_report_path = f"http://{node}:8000/reports/{job_id}/"
        try:
            response = requests.get(f"{node_report_path}list")
            if response.status_code != 200:
                continue
            xml_files = response.json().get("xml_files", [])
            for xml_file in xml_files:
                r = requests.get(f"{node_report_path}{xml_file}")
                if r.status_code == 200:
                    with open(os.path.join(report_dir, xml_file), 'wb') as f:
                        f.write(r.content)
        except Exception as e:
            print(f"Failed to fetch from {node}: {e}")

    from robot.rebot import rebot
    xml_paths = [os.path.join(report_dir, f) for f in os.listdir(report_dir) if f.endswith(".xml")]
    if xml_paths:
        merged_output = os.path.join(report_dir, "merged_output.xml")
        rebot(*xml_paths, output=merged_output)
    else:
        print("No XML files found to merge.")
        
def update_job_status(job_id: int):
    status_update_url = f"http://taskmanager.local/api/jobs/{job_id}/complete"
    response = requests.post(status_update_url)
    if response.status_code != 200:
        raise Exception(f"Failed to update job status for job {job_id}: {response.text}")
    print(f"Job {job_id} status updated to completed.")
    

def _allocate(**context):
    job_id = get_job_id_from_context(context)
    allocate_tasks(job_id)

def _wait(**context):
    job_id = get_job_id_from_context(context)
    success = wait_for_all_tasks(job_id)
    if not success:
        raise Exception("Timed out waiting for tasks to complete")

def _merge(**context):
    job_id = get_job_id_from_context(context)
    merge_xml_reports(job_id)

def _finalize(**context):
    job_id = get_job_id_from_context(context)
    update_job_status(job_id)

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    dag_id='job_execution_pipeline',
    default_args=default_args,
    description='Allocate job, run tasks remotely, wait, merge report, and update job status',
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['distributed', 'remote', 'job-execution']
)

with dag:
    allocate = PythonOperator(
        task_id='allocate_tasks',
        python_callable=_allocate,
        provide_context=True
    )

    wait = PythonOperator(
        task_id='wait_for_all_tasks',
        python_callable=_wait,
        provide_context=True
    )

    merge = PythonOperator(
        task_id='merge_xml_reports',
        python_callable=_merge,
        provide_context=True
    )

    finalize = PythonOperator(
        task_id='update_job_status',
        python_callable=_finalize,
        provide_context=True
    )

    allocate >> wait >> merge >> finalize
