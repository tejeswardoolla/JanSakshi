from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from app.core.config import utc_now

class OAuthState(Base):
    """
    PostgreSQL-backed secure OAuth state and PKCE verifier persistence.
    Enables OAuth authorization start and callback across separate serverless instances (Vercel Functions).
    Enforces TTL expiration, atomic single-use consumption, and replay protection.
    """
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    state_token = Column(String(255), unique=True, nullable=False, index=True)
    code_verifier = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    is_consumed = Column(Boolean, default=False, nullable=False, index=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        # Never expose state_token or code_verifier in string representations or logs
        return f"<OAuthState id={self.id} is_consumed={self.is_consumed}>"
