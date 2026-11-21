"""Imports every model so Alembic / Base.metadata sees all tables."""
from app.modules.foundation import models as _foundation  # noqa: F401  
from app.modules.announcements import models as _announcements  # noqa: F401
from app.modules.attendance import models as _attendance  # noqa: F401
from app.modules.leave import models as _leave  # noqa: F401
from app.modules.calendar import models as _calendar  # noqa: F401
from app.modules.complaints import models as _complaints  # noqa: F401
from app.modules.exams import models as _exams  # noqa: F401
from app.modules.fees import models as _fees  # noqa: F401
from app.modules.homework import models as _homework  # noqa: F401
from app.modules.notifications import models as _notifications  # noqa: F401
from app.modules.timetable import models as _timetable  # noqa: F401
