# File: /srv/apps/esign/init_db.py

from app.db.models import Base
from app.db.session import get_engine

if __name__ == "__main__":
    print("⏳ Creating database tables in 'esign'...")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created.")