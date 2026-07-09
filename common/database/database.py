# from psycopg2.pool import ThreadedConnectionPool
import os
import logging
import threading
import time
import psycopg2

logger = logging.getLogger()
logger.setLevel(logging.INFO)





#--esto maneja un pool de conexiones, pero no es optimo para entornos lambda
# class Database:
#     _pool = None
#     _pool_lock = threading.Lock()
#
#     @classmethod
#     def get_pool(cls):
#         if cls._pool is None:
#             with cls._pool_lock:
#                 if cls._pool is None:  # Double-check locking
#                     try:
#                         cls._pool = ThreadedConnectionPool(
#                             minconn=1,
#                             maxconn=10,
#                             host=os.getenv('DB_HOST'),
#                             port=os.getenv('DB_PORT'),
#                             user=os.getenv('DB_USER'),
#                             password=os.getenv('DB_PASSWORD'),
#                             database=os.getenv('DB_NAME'),
#                             sslmode='require'
#                         )
#                         logger.info("Database connection pool created")
#                     except Exception as e:
#                         logger.error(f"Error creating connection pool: {str(e)}")
#                         raise
#         return cls._pool
#
#     @classmethod
#     def close_pool(cls):
#         if cls._pool:
#             cls._pool.closeall()
#             cls._pool = None
#             logger.info("Database connection pool closed")
#
#

#--mucho mejor para entornos lambda con sus contras
class DatabaseSingletonConnection:
    """Maneja una única conexión reutilizable a la base de datos (ideal para entornos con poco paralelismo)."""

    _connection = None
    _last_used = None
    _lock = threading.Lock()
    CONNECTION_TIMEOUT = 300

    @classmethod
    def get_connection(cls):
        """Obtener conexión única y reutilizable para Lambda"""
        with cls._lock:
            current_time = time.time()

            # `psycopg2` expone `.closed` (0=open, !=0=cerrada).
            if cls._connection is None or getattr(cls._connection, "closed", 1) != 0 or cls._needs_refresh(current_time):
                cls._create_new_connection()

            cls._last_used = current_time
            return cls._connection

    @classmethod
    def _needs_refresh(cls, current_time: float) -> bool:
        """Verificar si la conexión necesita renovarse"""
        if cls._last_used is None:
            return True

        if current_time - cls._last_used > cls.CONNECTION_TIMEOUT:
            return True

        try:
            # `connection.execute(...)` NO existe en psycopg2; usar cursor.
            if cls._connection is None or getattr(cls._connection, "closed", 1) != 0:
                return True
            with cls._connection.cursor() as cur:
                cur.execute("SELECT 1;")
            return False
        except (psycopg2.Error, AttributeError):
            logger.info("Conexión perdida, creando nueva")
            return True

    @classmethod
    def _create_new_connection(cls):
        """Crear nueva conexión single con hasta 3 reintentos"""
        try:
            if cls._connection:
                cls._connection.close()
        except:
            pass

        max_retries = 3
        retry_delay = 2

        for attempt in range(1, max_retries + 1):
            try:
                cls._connection = psycopg2.connect(
                    host=os.getenv('DB_HOST'),
                    port=os.getenv('DB_PORT'),
                    user=os.getenv('DB_USER'),
                    password=os.getenv('DB_PASSWORD'),
                    database=os.getenv('DB_NAME'),
                    sslmode='require',
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=3
                )
                cls._connection.autocommit = False  # Transacciones explícitas
                logger.info(f"Nueva conexión creada para Lambda en intento {attempt}")
                return  # Salir si se conecta correctamente

            except Exception as e:
                logger.error(f"Error creando conexión en intento {attempt}: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error("Número máximo de reintentos alcanzado. No se pudo crear conexión.")
                    raise

    @classmethod
    def close_connection(cls):
        """Cerrar conexión manualmente"""
        with cls._lock:
            if cls._connection:
                try:
                    cls._connection.close()
                except:
                    pass
                cls._connection = None
                cls._last_used = None
                logger.info("Conexión cerrada")

