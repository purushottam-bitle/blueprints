from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from airflow.utils.context import Context
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from allocate_and_run_tasks import allocate_tasks, wait_for_all_tasks
from merge_reports import merge_xml_reports
from update_job_status import update_job_status

def get_job_id_from_context(context: Context):
    return int(context['dag_run'].conf.get('job_id'))

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
