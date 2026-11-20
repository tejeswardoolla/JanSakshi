import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import get_lock_engine, ensure_email_message_schema
from app.services.email.inbox_monitor import GmailSyncLock

class TestPostgresAdvisoryLockDedicated(unittest.TestCase):
    """
    Tests PostgreSQL advisory locking using dedicated SQLAlchemy connection.
    Verifies that application session db.commit() calls do not release the dedicated lock connection,
    proves mutual exclusion, and verifies connection invalidation on exceptions or failures.
    """

    def test_mock_engine_dedicated_connection_lifecycle(self):
        """Verifies that acquire() uses a dedicated connection, executes try_lock, unlock, commits, and closes."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        # Mock try_advisory_lock returns True, advisory_unlock returns True
        mock_conn.execute.side_effect = [
            MagicMock(scalar=lambda: True),   # pg_try_advisory_lock
            MagicMock(scalar=lambda: True),   # pg_advisory_unlock
        ]

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_engine

        # Acquire lock
        with GmailSyncLock.acquire(mock_session) as acquired:
            self.assertTrue(acquired)
            # Application session commits during sync
            mock_session.commit()
            mock_session.commit()
            # Verify lock connection was checked out and called try_lock + commit
            mock_engine.connect.assert_called_once()
            self.assertEqual(mock_conn.execute.call_count, 1)
            mock_conn.commit.assert_called_once()

        # After exiting with block: verify unlock was executed, committed, and closed
        self.assertEqual(mock_conn.execute.call_count, 2)
        mock_conn.close.assert_called_once()

    def test_mock_engine_acquisition_failure_closes_connection(self):
        """When pg_try_advisory_lock returns False, dedicated connection is immediately closed and False yielded."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        mock_conn.execute.return_value = MagicMock(scalar=lambda: False)

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_engine

        with GmailSyncLock.acquire(mock_session) as acquired:
            self.assertFalse(acquired)

        # Dedicated connection closed without executing unlock
        mock_conn.close.assert_called_once()

    def test_acquisition_exception_invalidates_connection(self):
        """When pg_try_advisory_lock raises an exception, connection must be invalidated and closed."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        mock_conn.execute.side_effect = Exception("Network timeout during lock acquisition")

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_engine

        with GmailSyncLock.acquire(mock_session) as acquired:
            self.assertFalse(acquired)

        mock_conn.invalidate.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_unlock_exception_invalidates_connection(self):
        """When pg_advisory_unlock raises an exception, connection must be invalidated to prevent leaking locked sessions."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        mock_conn.execute.side_effect = [
            MagicMock(scalar=lambda: True),  # acquire succeeds
            Exception("Connection reset during unlock"),  # unlock raises
        ]

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_engine

        with GmailSyncLock.acquire(mock_session) as acquired:
            self.assertTrue(acquired)

        mock_conn.invalidate.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_unlock_returned_false_invalidates_connection(self):
        """When pg_advisory_unlock returns False, connection must be invalidated."""
        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        mock_conn.execute.side_effect = [
            MagicMock(scalar=lambda: True),   # acquire succeeds
            MagicMock(scalar=lambda: False),  # unlock returned False
        ]

        mock_session = MagicMock()
        mock_session.get_bind.return_value = mock_engine

        with GmailSyncLock.acquire(mock_session) as acquired:
            self.assertTrue(acquired)

        mock_conn.invalidate.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_neon_pooler_endpoint_rejected_with_configuration_error(self):
        """Verifies that GMAIL_LOCK_DATABASE_URL rejecting pooled (-pooler) endpoints fails cleanly without credentials."""
        with patch.dict(os.environ, {
            "GMAIL_LOCK_DATABASE_URL": "postgresql://neondb_owner:secret_pw@ep-sample-pooler.us-east-1.aws.neon.tech/neondb"
        }):
            with patch("app.database.GMAIL_LOCK_DATABASE_URL", "postgresql://neondb_owner:secret_pw@ep-sample-pooler.us-east-1.aws.neon.tech/neondb"):
                with self.assertRaises(ValueError) as ctx:
                    get_lock_engine()
                # Confirm error message explains issue and NEVER prints secret password
                self.assertIn("pooled (-pooler) endpoint", str(ctx.exception))
                self.assertNotIn("secret_pw", str(ctx.exception))

    def test_live_postgres_advisory_lock_with_session_commits(self):
        """
        Integration test against real PostgreSQL (Neon DB direct endpoint).
        Proves:
        1. Lock is acquired on dedicated connection.
        2. Application session executes commits during sync without releasing the lock.
        3. A second connection CANNOT acquire the lock while sync is active.
        4. The second connection CAN acquire the lock after sync exits.
        """
        target_url = os.getenv("TARGET_DATABASE_URL", "").strip()
        if not target_url:
            env_file = os.path.join(backend_dir, ".env")
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    for line in f:
                        if line.startswith("TARGET_DATABASE_URL="):
                            target_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

        if not target_url or not target_url.startswith("postgres"):
            self.skipTest("TARGET_DATABASE_URL not configured with PostgreSQL; skipping live Neon test.")

        # Create isolated engine for integration testing with short connection timeout
        pg_engine = create_engine(target_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
        PgSession = sessionmaker(bind=pg_engine)
        app_session = PgSession()

        try:
            # Connectivity check: skip test gracefully if remote Neon endpoint is currently unreachable
            try:
                with pg_engine.connect() as test_conn:
                    test_conn.execute(text("SELECT 1"))
            except Exception as conn_err:
                self.skipTest(f"Remote Neon PostgreSQL endpoint is unreachable from this network ({conn_err}); skipping live Neon test.")

            # Step 1: Acquire lock using GmailSyncLock on app_session
            with GmailSyncLock.acquire(app_session) as acquired:
                self.assertTrue(acquired, "First acquisition on dedicated connection must succeed")

                # Step 2: Application session performs commits during sync
                app_session.execute(text("SELECT 1"))
                app_session.commit()
                app_session.execute(text("SELECT 2"))
                app_session.commit()

                # Step 3: Concurrent second connection attempts to acquire the same lock
                with pg_engine.connect() as conn2:
                    is_acquired_by_conn2 = bool(
                        conn2.execute(text(f"SELECT pg_try_advisory_lock({GmailSyncLock.ADVISORY_LOCK_ID})")).scalar()
                    )
                    self.assertFalse(
                        is_acquired_by_conn2,
                        "Concurrent second connection MUST NOT acquire advisory lock while first lock is active!"
                    )

            # Step 4: After exiting context manager, lock is released.
            # Second connection should now successfully acquire it.
            with pg_engine.connect() as conn3:
                is_acquired_by_conn3 = bool(
                    conn3.execute(text(f"SELECT pg_try_advisory_lock({GmailSyncLock.ADVISORY_LOCK_ID})")).scalar()
                )
                self.assertTrue(
                    is_acquired_by_conn3,
                    "Second connection MUST acquire advisory lock after first lock has completed!"
                )
                # Cleanup: release advisory lock
                conn3.execute(text(f"SELECT pg_advisory_unlock({GmailSyncLock.ADVISORY_LOCK_ID})"))

        finally:
            app_session.close()
            pg_engine.dispose()

class TestEnsureEmailMessageSchemaMigration(unittest.TestCase):
    """
    Tests non-destructive schema migration and loud failure guarantees for email_messages.
    Verifies existing records are preserved and startup aborts if migration fails.
    """

    def test_schema_migration_success_and_preserves_records(self):
        """Proves existing records are preserved completely and retry columns are added non-destructively."""
        temp_engine = create_engine("sqlite:///:memory:")
        with temp_engine.connect() as conn:
            # Create legacy table without retry columns
            conn.execute(text("""
                CREATE TABLE email_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gmail_message_id VARCHAR(255) NOT NULL,
                    subject VARCHAR(500),
                    acknowledgement_sent BOOLEAN DEFAULT 0
                )
            """))
            # Seed 3 existing records
            conn.execute(text("INSERT INTO email_messages (gmail_message_id, subject, acknowledgement_sent) VALUES ('msg_1', 'Pothole A', 0)"))
            conn.execute(text("INSERT INTO email_messages (gmail_message_id, subject, acknowledgement_sent) VALUES ('msg_2', 'Streetlight B', 1)"))
            conn.execute(text("INSERT INTO email_messages (gmail_message_id, subject, acknowledgement_sent) VALUES ('msg_3', 'Water C', 0)"))
            conn.commit()

        # Run non-destructive migration
        ensure_email_message_schema(bind=temp_engine)

        with temp_engine.connect() as conn:
            # Verify all 3 records are preserved intact
            rows = conn.execute(text("SELECT id, gmail_message_id, subject, acknowledgement_sent, acknowledgement_retry_count, acknowledgement_last_retry_at FROM email_messages ORDER BY id ASC")).fetchall()
            self.assertEqual(len(rows), 3)

            # Record 1
            self.assertEqual(rows[0][1], "msg_1")
            self.assertEqual(rows[0][2], "Pothole A")
            self.assertEqual(rows[0][3], 0)
            self.assertEqual(rows[0][4], 0)  # default value populated
            self.assertIsNone(rows[0][5])

            # Record 2
            self.assertEqual(rows[1][1], "msg_2")
            self.assertEqual(rows[1][2], "Streetlight B")
            self.assertEqual(rows[1][3], 1)
            self.assertEqual(rows[1][4], 0)

            # Record 3
            self.assertEqual(rows[2][1], "msg_3")
            self.assertEqual(rows[2][2], "Water C")
            self.assertEqual(rows[2][3], 0)

    def test_schema_migration_fails_loudly_on_sql_error(self):
        """When an unexpected SQL or connection error occurs, migration raises RuntimeError instead of swallowing it."""
        mock_engine = MagicMock()
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["email_messages"]
        mock_inspector.get_columns.return_value = [{"name": "id"}, {"name": "gmail_message_id"}]

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = Exception("database is locked: concurrent write conflict")
        mock_engine.connect.return_value = mock_conn

        with patch("sqlalchemy.inspect", return_value=mock_inspector):
            with self.assertRaises(RuntimeError) as ctx:
                ensure_email_message_schema(bind=mock_engine)
            self.assertIn("Database migration failure: unable to verify or create email_messages schema", str(ctx.exception))
            self.assertIn("database is locked", str(ctx.exception))

    def test_schema_migration_fails_if_columns_missing_after_run(self):
        """When post-migration verification discovers columns are still missing, raises RuntimeError."""
        mock_engine = MagicMock()
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["email_messages"]
        # Always returns only original columns, simulating failed DDL
        mock_inspector.get_columns.return_value = [{"name": "id"}, {"name": "gmail_message_id"}]

        mock_conn = MagicMock()
        mock_engine.connect.return_value = mock_conn

        with patch("sqlalchemy.inspect", return_value=mock_inspector):
            with self.assertRaises(RuntimeError) as ctx:
                ensure_email_message_schema(bind=mock_engine)
            self.assertIn("Post-migration schema verification failed", str(ctx.exception))

    def test_startup_lifespan_aborts_on_migration_failure(self):
        """When ensure_email_message_schema fails, FastAPI lifespan aborts startup clearly."""
        from app.main import lifespan
        mock_app = MagicMock()

        with patch("app.database.ensure_email_message_schema", side_effect=RuntimeError("Neon DDL execution failed")):
            with self.assertRaises(RuntimeError) as ctx:
                import asyncio
                async def run_lifespan():
                    async with lifespan(mock_app):
                        pass
                asyncio.run(run_lifespan())
            self.assertIn("Application startup aborted due to database initialization failure", str(ctx.exception))

    def test_concurrent_schema_migrations(self):
        """Simulate concurrent application startup across multiple worker processes calling ensure_email_message_schema."""
        import tempfile
        from concurrent.futures import ThreadPoolExecutor

        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db_path = temp_db.name
        temp_db.close()

        engine = create_engine(f"sqlite:///{temp_db_path}")
        try:
            # Create old schema with existing rows
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE email_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        gmail_message_id VARCHAR(100) UNIQUE,
                        subject VARCHAR(500),
                        sender_email VARCHAR(255),
                        received_at TIMESTAMP,
                        processing_status VARCHAR(50)
                    )
                """))
                conn.execute(text("""
                    INSERT INTO email_messages (gmail_message_id, subject, sender_email, received_at, processing_status)
                    VALUES
                    ('msg_c1', 'Concurrent Test 1', 'u1@example.com', '2026-11-20 00:00:00', 'processed'),
                    ('msg_c2', 'Concurrent Test 2', 'u2@example.com', '2026-11-20 00:00:00', 'processed')
                """))
                conn.commit()

            # Execute ensure_email_message_schema concurrently across 6 workers
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(ensure_email_message_schema, bind=engine) for _ in range(6)]
                for f in futures:
                    # Should complete without error
                    f.result()

            # Verify schema was updated properly with retry columns
            from sqlalchemy import inspect
            inspector = inspect(engine)
            cols = {c["name"] for c in inspector.get_columns("email_messages")}
            self.assertIn("acknowledgement_retry_count", cols)
            self.assertIn("acknowledgement_last_retry_at", cols)

            # Verify data was preserved
            with engine.connect() as conn:
                rows = conn.execute(text("SELECT id, gmail_message_id, subject, acknowledgement_retry_count FROM email_messages ORDER BY id ASC")).fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0][1], "msg_c1")
                self.assertEqual(rows[0][2], "Concurrent Test 1")
                self.assertEqual(rows[0][3], 0)
                self.assertEqual(rows[1][1], "msg_c2")
                self.assertEqual(rows[1][2], "Concurrent Test 2")
                self.assertEqual(rows[1][3], 0)
        finally:
            engine.dispose()
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                except Exception:
                    pass

if __name__ == "__main__":
    unittest.main()
