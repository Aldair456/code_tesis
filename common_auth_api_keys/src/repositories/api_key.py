from common.repositories.base import BaseRepository
from common.models.models import ApiKey

class ApiKeyRepository(BaseRepository[ApiKey]):
    def __init__(self):
        super().__init__("api_keys", ApiKey)

