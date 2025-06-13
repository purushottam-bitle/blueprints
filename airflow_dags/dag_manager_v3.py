from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from datetime import timedelta
import psycopg2

# ---------- CONFIG ----------

DB_CONFIG = {
    'host': 'host.docker.internal',
    'database': 'your_db',
    'user': 'your_user',
    'password': 'your_password'
}

# ---------- DEFAULT ARGS ----------

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# ---------- DAG ----------

dag = DAG(
    dag_id='job_manager_dag',
    default_args=default_args,
    description='Orchestrates job scheduling and triggers job_execution_pipeline DAG',
    schedule_interval='*/10 * * * *',  # every 10 minutes
    start_date=days_ago(1),
    catchup=False,
)

# ---------- TASK DEFINITIONS ----------

def fetch_queued_jobs(**context):
    """Fetch job_ids from the schedule table with 'queued' status"""
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


with dag:
    # Step 1: Fetch all queued job IDs
    fetch_jobs = PythonOperator(
        task_id='fetch_queued_jobs',
        python_callable=fetch_queued_jobs,
        provide_context=True,
    )

    # Step 2: Dynamically trigger job_execution_pipeline for each job_id
    def create_trigger_task(job_id):
        return TriggerDagRunOperator(
            task_id=f'trigger_job_{job_id}',
            trigger_dag_id='job_execution_pipeline',
            conf={"job_id": job_id},
            wait_for_completion=True,
            reset_dag_run=True
        )

    def trigger_all_jobs(**context):
        job_ids = context['ti'].xcom_pull(key='job_ids', task_ids='fetch_queued_jobs')
        for job_id in job_ids:
            create_trigger_task(job_id).execute(context=context)

    # Use a TaskGroup to group all triggers
    with TaskGroup("trigger_jobs_group") as trigger_jobs_group:
        trigger_all = PythonOperator(
            task_id="trigger_all_jobs",
            python_callable=trigger_all_jobs,
            provide_context=True
        )

    # DAG order
    fetch_jobs >> trigger_jobs_group
