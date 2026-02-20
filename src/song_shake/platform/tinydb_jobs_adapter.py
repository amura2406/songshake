"""TinyDB adapter wrapping jobs/storage free functions behind JobStoragePort."""

from song_shake.features.jobs import storage as job_storage
from song_shake.features.jobs.models import JobType


class TinyDBJobsAdapter:
    """Wraps song_shake.features.jobs.storage behind JobStoragePort Protocol."""

    def create_job(
        self,
        job_id: str,
        job_type: JobType,
        playlist_id: str,
        owner: str,
        playlist_name: str = "",
    ) -> dict:
        return job_storage.create_job(
            job_id=job_id,
            job_type=job_type,
            playlist_id=playlist_id,
            owner=owner,
            playlist_name=playlist_name,
        )

    def update_job(self, job_id: str, fields: dict) -> None:
        job_storage.update_job(job_id, fields)

    def get_job(self, job_id: str) -> dict | None:
        return job_storage.get_job(job_id)

    def get_active_jobs(self, owner: str | None = None) -> list[dict]:
        return job_storage.get_active_jobs(owner)

    def get_job_history(self, owner: str | None = None) -> list[dict]:
        return job_storage.get_job_history(owner)

    def get_job_for_playlist(
        self, playlist_id: str, owner: str | None = None
    ) -> dict | None:
        return job_storage.get_job_for_playlist(playlist_id, owner)

    def check_and_create_job(
        self,
        playlist_id: str,
        owner: str,
        job_id: str,
        job_type: JobType,
        playlist_name: str = "",
    ) -> dict | None:
        return job_storage.check_and_create_job(
            playlist_id=playlist_id,
            owner=owner,
            job_id=job_id,
            job_type=job_type,
            playlist_name=playlist_name,
        )

    def get_all_active_jobs(self) -> dict:
        return job_storage.get_all_active_jobs()

    def get_ai_usage(self, owner: str) -> dict:
        return job_storage.get_ai_usage(owner)

    def update_ai_usage(
        self,
        owner: str,
        input_tokens_delta: int,
        output_tokens_delta: int,
        cost_delta: float,
    ) -> dict:
        return job_storage.update_ai_usage(
            owner, input_tokens_delta, output_tokens_delta, cost_delta
        )
