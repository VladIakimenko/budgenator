import celery
import config

celery_app = celery.Celery(
    main="budgenator",
    broker=config.BROKER_CONN_STRING,
    backend=config.RESULT_BACKEND_CONN_STRING,
)
celery_app.conf |= {"beat_dburi": config.BEAT_DB_CONN_STRING}
