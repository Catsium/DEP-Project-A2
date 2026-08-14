import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = "postgresql://postgres.dkmgggsbnpxmudvpshle:nigni9-cutvoh-vathYt@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={"sslmode": "require"}
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)