from core.db.base import Base
from core.db.session import engine

import core.models.video
import core.models.rendition
import core.models.job

Base.metadata.create_all(bind=engine)
