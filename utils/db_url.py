from typing import Any, Dict
from utils import db2_bootstrap


SQLALCHEMY_DRIVERS = {
    "PostgreSQL": "postgresql+psycopg2",
    "MySQL": "mysql+pymysql",
    "MariaDB": "mariadb+pymysql",
    "MSSQL": "mssql+pymssql",
    "Oracle": "oracle+oracledb",
    "DB2": "ibm_db_sa",
}


def build_sqlalchemy_url(db_type: str, fields: Dict[str, Any]) -> str:
    """Build a SQLAlchemy URL string from decrypted credential fields."""
    from sqlalchemy.engine import URL

    if db_type == "DB2":
        db2_bootstrap.register()

    query = {}
    database = fields["database"]
    if db_type == "Oracle":
        query["service_name"] = database
        database = None

    return URL.create(
        drivername=SQLALCHEMY_DRIVERS[db_type],
        username=fields["user"],
        password=fields["password"],
        host=fields["host"],
        port=int(fields["port"]) if fields.get("port") else None,
        database=database,
        query=query,
    ).render_as_string(hide_password=False)
