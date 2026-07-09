from common_auth_api_keys.src.repositories.api_key import ApiKeyRepository
from common_auth_api_keys.src.services.api_key import ApiKeyAuthService







def get_api_key_auth_service():
    api_key_repository = ApiKeyRepository()
    return ApiKeyAuthService(
        api_key_repository=api_key_repository,
        )

