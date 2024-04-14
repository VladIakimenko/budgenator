# Set up and launch
Set variables in .env  
If using postgres or mysql, use `createdb` to create the databases in accordance with .env
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
python init_db.py

```

# Celery
```
celery worker -A task_manager.celery_config
$ celery beat -A task_manager.celery_config -S celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler
```

# Requirements
Designed with `python 3.11`  
Minimal required `python 3.6`
