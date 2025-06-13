from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import subprocess
import psycopg2
import os
import time

# ---------- CONFIG ----------

DB_CONFIG = {
    'host': 'host.docker.internal',
    'database': 'your_db',
    'user': 'your_user',
    'password': 'your_password'
}

REPORT_BASE_PATH = "/path/to/reports"

# ---------- DEFAULT ARGS ----------

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# ---------- DAG ----------

dag = DAG(
    'job_manager_dag',
    default_args=default_args,
    description='Orchestrates job scheduling and reporting',
    schedule_interval='*/10 * * * *',  # every 10 mins
    start_date=days_ago(1),
    catchup=False,
)

# ---------- TASK FUNCTIONS ----------

def fetch_queued_jobs(**context):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT id FROM schedule WHERE status = 'queued'")
    jobs = cur.fetchall()
    cur.close()
    conn.close()
    job_ids = [job[0] for job in jobs]
    if not job_ids:
        raise ValueError("No queued jobs found")
    context['ti'].xcom_push(key='job_ids', value=job_ids)

def allocate_and_start_tasks(**context):
    job_ids = context['ti'].xcom_pull(key='job_ids', task_ids='fetch_queued_jobs')
    for job_id in job_ids:
        subprocess.run(['python3', 'allocate_and_run_tasks.py', str(job_id)], check=True)

def wait_for_task_completion(**context):
    job_ids = context['ti'].xcom_pull(key='job_ids', task_ids='fetch_queued_jobs')
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    for job_id in job_ids:
        while True:
            cur.execute("SELECT COUNT(*) FROM tasks WHERE job_id = %s AND status != 'completed'", (job_id,))
            count = cur.fetchone()[0]
            if count == 0:
                break
            time.sleep(10)
    cur.close()
    conn.close()

def merge_task_reports(**context):
    job_ids = context['ti'].xcom_pull(key='job_ids', task_ids='fetch_queued_jobs')
    for job_id in job_ids:
        output_dir = os.path.join(REPORT_BASE_PATH, str(job_id))
        output_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.xml')]
        merged_output = os.path.join(output_dir, 'merged_output.xml')
        cmd = ['rebot', '--merge'] + output_files + ['--output', merged_output]
        subprocess.run(cmd, check=True)

def mark_job_complete(**context):
    job_ids = context['ti'].xcom_pull(key='job_ids', task_ids='fetch_queued_jobs')
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    for job_id in job_ids:
        cur.execute("UPDATE schedule SET status = 'completed' WHERE id = %s", (job_id,))
    conn.commit()
    cur.close()
    conn.close()

# ---------- TASK DEFINITIONS ----------

fetch_jobs = PythonOperator(
    task_id='fetch_queued_jobs',
    python_callable=fetch_queued_jobs,
    provide_context=True,
    dag=dag
)

start_tasks = PythonOperator(
    task_id='allocate_and_start_tasks',
    python_callable=allocate_and_start_tasks,
    provide_context=True,
    dag=dag
)

wait_tasks = PythonOperator(
    task_id='wait_for_task_completion',
    python_callable=wait_for_task_completion,
    provide_context=True,
    dag=dag
)

merge_reports = PythonOperator(
    task_id='merge_task_reports',
    python_callable=merge_task_reports,
    provide_context=True,
    dag=dag
)

complete_job = PythonOperator(
    task_id='mark_job_complete',
    python_callable=mark_job_complete,
    provide_context=True,
    dag=dag
)

# ---------- DAG PIPELINE ----------

fetch_jobs >> start_tasks >> wait_tasks >> merge_reports >> complete_job
