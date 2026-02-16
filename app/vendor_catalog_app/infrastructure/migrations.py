"""
Database Migration Management

Provides utilities for applying and tracking database schema migrations.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Manages database schema migrations."""

    def __init__(self, repository):
        """
        Initialize migration runner.
        
        Args:
            repository: Repository instance with database connection
        """
        self.repo = repository
        self.migrations_dir = Path("setup/databricks")

    def get_current_version(self) -> int:
        """
        Get current schema version from database.
        
        Returns:
            Current version number, or 0 if no migrations applied
        """
        try:
            result = self.repo._execute_read(
                "SELECT MAX(version_number) as version FROM twvendor.app_schema_version"
            )
            if result and result[0]['version']:
                return int(result[0]['version'])
            return 0
        except Exception as e:
            logger.warning(f"Could not read schema version: {e}")
            return 0

    def get_migration_files(self) -> list[Path]:
        """
        Get list of migration files, sorted by version number.
        
        Returns:
            List of Path objects for migration files
        """
        if not self.migrations_dir.exists():
            return []

        migration_files = list(self.migrations_dir.glob("migration_*.sql"))

        # Sort by version number extracted from filename
        def get_version(path: Path) -> int:
            # Extract number from migration_NNN_description.sql
            name = path.stem
            parts = name.split('_')
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    return 0
            return 0

        return sorted(migration_files, key=get_version)

    def apply_migration(self, migration_file: Path) -> bool:
        """
        Apply a single migration file.
        
        Args:
            migration_file: Path to migration SQL file
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Applying migration: {migration_file.name}")

        try:
            with open(migration_file, encoding='utf-8') as f:
                sql = f.read()

            # Execute migration SQL
            # Note: This assumes migration includes schema version insert
            self.repo._execute_write(sql)

            logger.info(f"Migration {migration_file.name} applied successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to apply migration {migration_file.name}: {e}")
            return False

    def apply_pending_migrations(self) -> int:
        """
        Apply all migrations newer than current schema version.
        
        Returns:
            Number of migrations applied
        """
        current_version = self.get_current_version()
        logger.info(f"Current schema version: {current_version}")

        migration_files = self.get_migration_files()
        applied_count = 0

        for migration_file in migration_files:
            # Extract version from filename
            migration_version = self._get_migration_version(migration_file)

            if migration_version > current_version:
                logger.info(f"Applying migration {migration_version}: {migration_file.name}")

                if self.apply_migration(migration_file):
                    applied_count += 1
                else:
                    logger.error(f"Migration {migration_version} failed, stopping")
                    break

        if applied_count > 0:
            new_version = self.get_current_version()
            logger.info(f"Applied {applied_count} migrations. New version: {new_version}")
        else:
            logger.info("No pending migrations")

        return applied_count

    def verify_schema_version(self, expected_version: int) -> bool:
        """
        Verify that database schema is at expected version.
        
        Args:
            expected_version: Expected schema version number
        
        Returns:
            True if current version >= expected version
        
        Raises:
            RuntimeError: If schema version is too old
        """
        current_version = self.get_current_version()

        if current_version < expected_version:
            raise RuntimeError(
                f"Database schema out of date. "
                f"Expected version {expected_version}, found {current_version}. "
                f"Apply pending migrations."
            )

        if current_version > expected_version:
            logger.warning(
                f"Database schema newer than expected. "
                f"Expected {expected_version}, found {current_version}. "
                f"Update application code."
            )

        return True

    def _get_migration_version(self, migration_file: Path) -> int:
        """Extract version number from migration filename."""
        name = migration_file.stem
        parts = name.split('_')
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                return 0
        return 0

    def get_migration_history(self) -> list[dict]:
        """
        Get history of applied migrations.
        
        Returns:
            List of migration records with version, description, applied_at
        """
        try:
            return self.repo._execute_read(
                """
                SELECT version_number, description, applied_by, applied_at
                FROM twvendor.app_schema_version
                ORDER BY applied_at DESC
                """
            )
        except Exception as e:
            logger.error(f"Could not fetch migration history: {e}")
            return []


def verify_schema_on_startup(repository, expected_version: int):
    """
    Verify schema version on application startup.
    
    Usage in app/main.py:
        @app.on_event("startup")
        async def startup():
            verify_schema_on_startup(repo, expected_version=7)
    
    Args:
        repository: Repository instance
        expected_version: Minimum required schema version
    
    Raises:
        RuntimeError: If schema version is too old
    """
    runner = MigrationRunner(repository)
    runner.verify_schema_version(expected_version)
    logger.info(f"Schema version verification passed: v{runner.get_current_version()}")
