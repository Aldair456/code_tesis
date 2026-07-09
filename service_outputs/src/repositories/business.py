from common.repositories.base import BaseRepository
from common.models.models import Business
class BusinessRepository(BaseRepository[Business]):
    def __init__(self):
        super().__init__("businesses", Business)
