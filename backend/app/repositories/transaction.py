from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction


class TransactionRepository:
    @staticmethod
    async def get_by_job_id(
        db: AsyncSession,
        job_id: UUID,
        category: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        account_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Transaction]:
        conditions = [Transaction.job_id == job_id]
        
        if category is not None:
            conditions.append(Transaction.category == category)
            
        if is_anomaly is not None:
            conditions.append(Transaction.is_anomaly == is_anomaly)
            
        if account_id is not None:
            conditions.append(Transaction.account_id == account_id)
            
        stmt = (
            select(Transaction)
            .where(and_(*conditions))
            .offset(skip)
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
        
    @staticmethod
    async def count_by_job_id(
        db: AsyncSession,
        job_id: UUID,
        category: Optional[str] = None,
        is_anomaly: Optional[bool] = None,
        account_id: Optional[str] = None
    ) -> int:
        from sqlalchemy import func
        conditions = [Transaction.job_id == job_id]
        
        if category is not None:
            conditions.append(Transaction.category == category)
            
        if is_anomaly is not None:
            conditions.append(Transaction.is_anomaly == is_anomaly)
            
        if account_id is not None:
            conditions.append(Transaction.account_id == account_id)
            
        stmt = select(func.count(Transaction.id)).where(and_(*conditions))
        result = await db.execute(stmt)
        return result.scalar() or 0
