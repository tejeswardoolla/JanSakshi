from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.config import utc_now

class Department(Base):
    """
    Municipal Department entity responsible for civic issue resolution.
    (e.g., Roads & Public Works, Sanitation, Water Supply, Drainage, Electrical)
    """
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    code = Column(String(32), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    head_name = Column(String(128), nullable=True)
    contact_email = Column(String(128), nullable=True)
    sla_days = Column(Integer, default=7, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    users = relationship("User", back_populates="department")
    complaints = relationship("Complaint", back_populates="department")

class User(Base):
    """
    Administrative / Municipal authority user account.
    Supports Role-Based Access Control (RBAC): admin, authority_officer, department_officer.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="authority_officer")  # admin, authority_officer, department_officer
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    allowed_department_ids = Column(String(128), nullable=True)  # Comma-separated IDs (e.g. "1,2,3,4,5,6" for demo lead)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    department = relationship("Department", back_populates="users")

    def get_authorized_department_ids(self) -> list[int]:
        """
        Returns list of department IDs the user is explicitly authorized to access.
        - admin & authority_officer: all 6 departments [1, 2, 3, 4, 5, 6]
        - department_officer with allowed_department_ids (e.g. dept_demo): [1, 2, 3, 4, 5, 6]
        - standard department officer (e.g. roads_officer): only [department_id] (e.g. [1])
        """
        if self.role in ("admin", "authority_officer"):
            return [1, 2, 3, 4, 5, 6]
        if self.username == "dept_demo" or self.allowed_department_ids == "all":
            return [1, 2, 3, 4, 5, 6]
        if self.allowed_department_ids:
            try:
                return [int(x.strip()) for x in self.allowed_department_ids.split(",") if x.strip()]
            except Exception:
                pass
        if self.department_id:
            return [self.department_id]
        return []

class RevokedToken(Base):
    """
    Tracks cryptographically revoked JWT identifiers (jti) for server-enforced logout,
    session termination, and refresh token rotation invalidation.
    """
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    token_type = Column(String(16), default="access", nullable=False)  # "access" or "refresh"
    username = Column(String(64), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


