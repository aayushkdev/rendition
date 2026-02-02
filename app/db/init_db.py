from app.db.base import Base
from app.db.session import engine

import app.models.video
import app.models.rendition
import app.models.job

Base.metadata.create_all(bind=engine)
