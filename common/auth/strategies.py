from abc import ABC, abstractmethod

class AuthorizationStrategy(ABC):
    @abstractmethod
    def is_authorized(self, user, required_permission) -> bool:
        pass


ROLE_HIERARCHY = {
    "ADMIN": 4,
    "GERENCIA": 3,
    "SUPERVISOR": 2,
    "ANALYST": 1
}

class RoleHierarchyStrategy(AuthorizationStrategy):
    def is_authorized(self, user, required_permission):
        user_roles = user.get("roles", [])
        required_level = ROLE_HIERARCHY.get(
            str(required_permission).strip().upper(), 0
        )

        return any(
            ROLE_HIERARCHY.get(str(role).strip().upper(), 0) >= required_level
            for role in user_roles
        )

class RoleListStrategy(AuthorizationStrategy):
    def is_authorized(self, user, required_roles):
        return any(role in required_roles for role in user.get("roles", []))


