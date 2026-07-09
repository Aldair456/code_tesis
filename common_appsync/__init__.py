"""
Cliente común para notificar a AWS AppSync (GraphQL).
Cualquier Lambda o servicio puede usarlo pasando endpoint y api_key.
"""
from common_appsync.appsync_client import AppSyncClient

__all__ = ["AppSyncClient"]
