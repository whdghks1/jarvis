import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["AUTH_REQUIRED"] = "false"
os.environ.pop("OPENAI_MODEL", None)
