# Schema migration reproducibility

This project now ships with an Alembic migration chain rooted at `0001_initial_schema`.

## Reproducibility workflow

Run these commands from repository root:

```bash
DATABASE_URL=sqlite:///./leonardo_migration_test.db uv run alembic upgrade head
DATABASE_URL=sqlite:///./leonardo_migration_test.db uv run alembic downgrade base
DATABASE_URL=sqlite:///./leonardo_migration_test.db uv run alembic upgrade head
```

The workflow proves that schema setup is deterministic and reproducible from an empty database.

## Tables created

- `tasks`
- `papers`
- `reports`
