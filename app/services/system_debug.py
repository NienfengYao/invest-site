from sqlalchemy import inspect, text

from sqlalchemy import inspect, text


def get_system_db_summary(db):
    inspector = inspect(db.bind)

    tables = []

    for table_name in sorted(inspector.get_table_names()):

        columns = inspector.get_columns(table_name)

        row_count = db.execute(
            text(f'SELECT COUNT(*) FROM "{table_name}"')
        ).scalar()

        tables.append({
            "name": table_name,
            "row_count": row_count,
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable"),
                    "primary_key": col.get("primary_key"),
                }
                for col in columns
            ],
        })

    return tables
