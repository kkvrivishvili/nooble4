from typing import ClassVar
from common.config.base_settings import CommonAppSettings

class QueryServiceSettings(CommonAppSettings):
    """
    Settings specific to the Query Service.
    """
    service_name: ClassVar[str] = "query_service"
