from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from allocate_and_run_tasks import allocate_tasks, wait_for_all_tasks
from merge_reports import merge_xml_reports
from update_job_status import update_job_status

JOB_ID = 123  # this can be dynamically pulled or templated in advanced setups

def _allocate():
    allocate_tasks(JOB_ID)

def _wait():
    success = wait_for_all_tasks(JOB_ID)
    if not success:
        raise Exception("Timed out waiting for tasks to complete")

def _merge():
    merge_xml_reports(JOB_ID)

def _finalize():
    update_job_status(JOB_ID)

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
        python_callable=_allocate
    )

    wait = PythonOperator(
        task_id='wait_for_all_tasks',
        python_callable=_wait
    )

    merge = PythonOperator(
        task_id='merge_xml_reports',
        python_callable=_merge
    )

    finalize = PythonOperator(
        task_id='update_job_status',
        python_callable=_finalize
    )

    allocate >> wait >> merge >> finalize
