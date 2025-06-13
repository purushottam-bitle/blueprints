def allocate_tasks(job_id: int, retry_delay: int = 60):
    import time

    create_url = f"http://taskmanager.local/api/jobs/{job_id}/allocate"
    response = requests.post(create_url)
    if response.status_code != 200:
        raise Exception(f"Failed to allocate tasks for job {job_id}: {response.text}")
    
    tasks = response.json().get("tasks", [])
    if not tasks:
        raise Exception(f"No tasks returned for job {job_id}")

    print(f"Tasks created for job {job_id}: {[t['task_id'] for t in tasks]}")

    for task in tasks:
        task_id = task['task_id']
        allocated = False

        while not allocated:
            try:
                alloc_url = f"http://taskmanager.local/api/tasks/{task_id}/allocate-device"
                alloc_response = requests.post(alloc_url)

                if alloc_response.status_code == 200:
                    device_info = alloc_response.json()
                    testbed_ip = device_info.get("testbed_ip")
                    print(f"Task {task_id} allocated on {testbed_ip}")

                    # Start task on testbed
                    start_url = f"http://{testbed_ip}/api/tasks/{task_id}/start"
                    start_response = requests.post(start_url)

                    if start_response.status_code == 200:
                        print(f"Started task {task_id} on {testbed_ip}")
                        allocated = True
                    else:
                        print(f"Start failed: {start_response.text}")
                else:
                    print(f"Allocation not ready: {alloc_response.text}")

            except Exception as e:
                print(f"Error allocating or starting task {task_id}: {e}")

            if not allocated:
                print(f"Retrying task {task_id} allocation in {retry_delay} seconds...")
                time.sleep(retry_delay)


def wait_for_all_tasks(job_id: int, poll_interval: int = 60, max_wait_hours: int = 24):
    import time

    timeout = max_wait_hours * 3600
    task_manager_status_url = f"http://taskmanager.local/api/jobs/{job_id}/status"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(task_manager_status_url)
            if response.status_code != 200:
                print(f"Status check failed: {response.text}")
            else:
                status = response.json().get("status")
                print(f"Job {job_id} status: {status}")
                if status == "completed":
                    print(f"All tasks completed for job {job_id}")
                    return True
        except Exception as e:
            print(f"Polling error: {e}")
        
        time.sleep(poll_interval)

    raise Exception(f"Timeout: Job {job_id} didn't complete in {max_wait_hours} hours")
