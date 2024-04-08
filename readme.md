# Not implemented yet

# Celery
```
celery worker -A core.celery_config
$ celery beat -A core.celery_config -S celery_sqlalchemy_scheduler.schedulers:DatabaseScheduler
```

# Requirements
Designed with `python 3.11`
Minimal required `python 3.6`
