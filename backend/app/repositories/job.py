from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.summary import JobSummary


class JobRepository:
    @staticmethod
    async def get_by_id(db: AsyncSession, job_id: UUID) -> Optional[Job]:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, filename: str, filesize: int) -> Job:
        job = Job(filename=filename, filesize=filesize, status="PENDING", progress=0)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def get_multi(db: AsyncSession, skip: int = 0, limit: int = 10) -> List[Job]:
        stmt = select(Job).order_by(desc(Job.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_summary_by_job_id(db: AsyncSession, job_id: UUID) -> Optional[JobSummary]:
        stmt = select(JobSummary).where(JobSummary.job_id == job_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
