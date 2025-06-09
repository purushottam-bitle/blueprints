Great — since **PostgreSQL and NGINX are already installed directly on your Ubuntu host**, we can **simplify the Docker setup** by:

1. **Using your host PostgreSQL** (instead of a Dockerized one).
2. **Skipping Docker for NGINX**, and configuring your existing NGINX to reverse proxy to the Airflow webserver Docker container.

---

## ✅ Updated Setup Overview

* Airflow runs in **Docker containers** (`webserver`, `scheduler`).
* Airflow connects to **host PostgreSQL** (ensure it’s accessible from Docker).
* Your existing **NGINX** reverse proxies to `localhost:<port>` where Airflow is running.

---

## 🔧 Step-by-Step Setup

### 1. Ensure Host PostgreSQL Accepts Docker Connections

Modify PostgreSQL's config:

* **`/etc/postgresql/13/main/postgresql.conf`**

  ```conf
  listen_addresses = '*'
  ```
* **`/etc/postgresql/13/main/pg_hba.conf`**
  Add:

  ```
  host  all  all  172.17.0.0/16  md5
  ```

Then restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

Create a database + user for Airflow:

```bash
sudo -u postgres psql
CREATE DATABASE airflow;
CREATE USER airflow WITH PASSWORD 'airflow';
GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
\q
```

---

### 2. Docker Compose (no Postgres or NGINX)

```yaml
# docker-compose.yml
version: '3.8'

services:
  airflow-webserver:
    image: apache/airflow:3.0.1-python3.10
    restart: always
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@host.docker.internal/airflow
      AIRFLOW__CORE__FERNET_KEY: ''
      AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
      AIRFLOW__WEBSERVER__RBAC: 'true'
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
    ports:
      - "8080:8080"
    entrypoint: >
      /bin/bash -c "airflow db upgrade &&
                    airflow users create --username admin --firstname Airflow --lastname Admin --role Admin --email admin@example.com --password admin || true &&
                    airflow webserver"
    networks:
      - airflow

  airflow-scheduler:
    image: apache/airflow:3.0.1-python3.10
    restart: always
    depends_on:
      - airflow-webserver
    environment:
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
      AIRFLOW__CORE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@host.docker.internal/airflow
    volumes:
      - ./airflow/dags:/opt/airflow/dags
      - ./airflow/logs:/opt/airflow/logs
      - ./airflow/plugins:/opt/airflow/plugins
    command: scheduler
    networks:
      - airflow

networks:
  airflow:
    driver: bridge
```

> 🔁 `host.docker.internal` works on Docker Desktop or newer Linux setups. If it fails, replace it with your host's IP (e.g., `172.17.0.1` or `localhost` with appropriate Docker network flags).

---

### 3. NGINX Host Config (outside Docker)

Add this to your existing **NGINX config** on Ubuntu (`/etc/nginx/sites-available/airflow.conf`):

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Or IP address

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/airflow.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## ✅ Final Steps

```bash
docker compose up -d
```

* Airflow UI: `http://your-server-ip/`
* Default Login: `admin / admin`

---

Would you like me to generate the directory structure or upload a zipped starter pack for this exact configuration?
