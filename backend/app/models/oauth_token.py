from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from app.database import Base
from app.core.config import utc_now

class OAuthToken(Base):
    """
    PostgreSQL-backed secure OAuth token persistence.
    Allows Gmail OAuth credentials and token refresh operations to survive
    ephemeral serverless invocations (Vercel Functions).
    """
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    provider = Column(String(64), nullable=False, index=True, default="gmail")
    account_email = Column(String(255), nullable=False, index=True)
    token_data = Column(Text, nullable=False)  # JSON-serialized credentials

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "account_email", name="uq_oauth_provider_email"),
    )
