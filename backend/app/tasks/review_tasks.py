from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def generate_review_draft(self, review_id: str) -> None:
    """Stub — full implementation in task 3.2."""
    pass


@celery_app.task(bind=True, max_retries=3)
def compute_sentiment(self, event_id: str, text: str) -> None:
    """Stub — full implementation in task 3.7."""
    pass
