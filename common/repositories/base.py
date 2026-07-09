from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from typing import Generic, TypeVar, Type, List, Dict, Any, Optional, Union, Tuple
from contextlib import contextmanager
from psycopg2.extras import RealDictCursor, Json
from common.database.database import DatabaseSingletonConnection

T = TypeVar('T')


class BaseRepository(Generic[T]):
    def __init__(self, table_name: str, model_class: Type[T]):
        self.table_name = table_name
        self.model_class = model_class

    def _get_connection(self):
        """Obtiene la conexión singleton directamente"""
        return DatabaseSingletonConnection.get_connection()

    def _convert_value_for_sql(self, value: Any) -> Any:
        """
        Convierte valores Python a formatos compatibles con SQL
        Solo maneja primer nivel - más eficiente y práctico para BDs relacionales
        """
        if value is None:
            return None

        if isinstance(value, UUID):
            return str(value)

        if isinstance(value, dict):
            return Json(value)

        if isinstance(value, list):
            # Si la lista contiene solo primitivos (int, str, float, bool), 
            # dejarla como lista para que psycopg2 la maneje como array de PostgreSQL
            # Si contiene objetos complejos (dict, list), convertirla a JSON
            if value and any(isinstance(item, (dict, list)) for item in value):
                return Json(value)
            # Lista vacía o de primitivos: dejar como lista para arrays de PostgreSQL
            return value

        if isinstance(value, (tuple, set)):
            # Convertir a lista y aplicar misma lógica
            list_value = list(value)
            if list_value and any(isinstance(item, (dict, list)) for item in list_value):
                return Json(list_value)
            return list_value

        if isinstance(value, (datetime, date, time, Decimal, bool)):
            return value

        return value

    def _prepare_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara los datos convirtiendo tipos incompatibles
        """
        return {key: self._convert_value_for_sql(val) for key, val in data.items()}

    def _prepare_data_list(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepara una lista de datos convirtiendo tipos incompatibles
        """
        return [self._prepare_data(data) for data in data_list]

    def _validate_fields(self, data: Dict[str, Any], operation: str = "operación") -> None:
        """Valida que los campos de datos estén en el modelo"""
        if not data:
            raise ValueError(f"No se proporcionaron datos para {operation}")

        self._validate_attributes(data, operation)

    def _validate_attributes(self, attributes: Union[Dict[str, Any], List[str], str],
                             operation: str = "operación",
                             exclude_id: bool = False) -> None:
        """
        Valida que los atributos proporcionados estén en el modelo y sean seguros

        Args:
            attributes: Puede ser:
                - Dict[str, Any]: Se validarán las keys
                - List[str]: Se validará cada string
                - str: Se validará el string individual
            operation: Nombre de la operación para mensajes de error
            exclude_id: Si True, excluye 'id' de los campos permitidos

        Raises:
            ValueError: Si hay atributos no permitidos o nombres inseguros
        """
        # Normalizar entrada a lista
        if isinstance(attributes, dict):
            attr_list = list(attributes.keys())
        elif isinstance(attributes, str):
            attr_list = [attributes]
        else:
            attr_list = list(attributes)

        if not attr_list:
            return

        # Obtener campos permitidos
        allowed_fields = set(self.model_class.model_fields.keys())
        if exclude_id:
            allowed_fields.discard('id')

        # Validar que estén en el modelo
        invalid_fields = [attr for attr in attr_list if attr not in allowed_fields]
        if invalid_fields:
            raise ValueError(
                f"Atributos no permitidos en {operation}: {', '.join(sorted(invalid_fields))}. "
                f"Campos válidos: {', '.join(sorted(allowed_fields))}"
            )

        # Validar nombres seguros (solo letras, números y guiones bajos)
        unsafe_fields = [attr for attr in attr_list if not attr.replace('_', '').isalnum()]
        if unsafe_fields:
            raise ValueError(
                f"Nombres de atributo inseguros en {operation}: {', '.join(unsafe_fields)}. "
                f"Solo se permiten letras, números y guiones bajos."
            )

    def _build_order_clause(
            self,
            order_by: Optional[Union[str, List[str], List[Tuple[str, str]]]],
    ) -> str:
        """
        Construye la cláusula ORDER BY de forma segura.

        Args:
            order_by: Especificación del ordenamiento

        Returns:
            str: Cláusula ORDER BY (puede ser string vacío)

        Raises:
            ValueError: Si hay atributos no permitidos o direcciones inválidas
        """
        if not order_by:
            return ""

        order_parts = []

        # normalizar entrada a lista de tuplas
        if isinstance(order_by, str):
            order_items = [(order_by, "ASC")]
        elif isinstance(order_by, tuple):
            if len(order_by) != 2:
                raise ValueError(f"Formato inválido en order_by (esperado 2 elementos, recibido {len(order_by)}): {order_by}")
            order_items = [order_by]
        elif isinstance(order_by, list):
            order_items = []
            for item in order_by:
                if isinstance(item, str):
                    order_items.append((item, "ASC"))
                elif isinstance(item, tuple) and len(item) == 2:
                    order_items.append(item)
                else:
                    raise ValueError(f"Formato inválido en order_by: {item}")
        else:
            raise ValueError(f"order_by debe ser str, List[str] o List[Tuple[str, str]], recibido: {type(order_by)}")

        # Validar cada item
        for attr, direction in order_items:
            # Validar atributo usando la función centralizada
            self._validate_attributes(attr, "validate order")

            # Validar dirección
            direction = direction.upper()
            if direction not in ("ASC", "DESC"):
                raise ValueError(f"Dirección de orden inválida: '{direction}'. Solo ASC o DESC")

            order_parts.append(f"{attr} {direction}")

        return f"ORDER BY {', '.join(order_parts)}" if order_parts else ""

    @contextmanager
    def transaction(self):
        """
        Context manager para transacciones.
        Uso: with repo.transaction() as tx:
                 tx.create(data1)
                 tx.update(id, data2)
        """
        conn = self._get_connection()
        try:
            tx = TransactionContext(self, conn)
            yield tx
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _execute_query(self, query: str, params: tuple = None) -> List[dict]:
        """Ejecuta una consulta y devuelve múltiples registros"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            conn.rollback()
            raise

    def _execute_query_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """Ejecuta una consulta y devuelve un solo registro"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        except Exception as e:
            conn.rollback()
            raise

    def _execute_command(self, query: str, params: tuple = None) -> int:
        """Ejecuta un comando (INSERT,INSERT MANY, UPDATE, DELETE)"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise

    def _execute_command_return(self, query: str, params: tuple = None) -> dict:
        """Ejecuta un comando (INSERT, UPDATE) que retorna una fila"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                conn.commit()
                return result
        except Exception as e:
            conn.rollback()
            raise

    # -- MÉTODOS CON CONEXIÓN ESPECÍFICA (PARA TRANSACCIONES) --
    def _execute_command_with_conn(self, conn, query: str, params: tuple = None) -> int:
        """Ejecuta un comando usando conexión específica (sin commit automático)"""
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def _execute_command_return_with_conn(self, conn, query: str, params: tuple = None) -> dict:
        """Ejecuta un comando que retorna usando conexión específica (sin commit automático)"""
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    # -- MÉTODOS PÚBLICOS CON CONVERSIÓN AUTOMÁTICA --
    def find_by_id(self, id: str) -> Optional[T]:
        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        query = f"SELECT * FROM {self.table_name} WHERE id = %s"
        record = self._execute_query_one(query, (id,))
        return self.model_class(**record) if record else None

    def find_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        if limit < 0 or offset < 0:
            raise ValueError("Limit y offset deben ser >= 0")

        query = f"SELECT * FROM {self.table_name} LIMIT %s OFFSET %s"
        records = self._execute_query(query, (limit, offset))
        return [self.model_class(**r) for r in records]

    def create(self, data: Dict[str, Any]) -> T:
        # -- valida campos con el modelo
        self._validate_fields(data, "create")

        # -- prepara data
        prepared_data = self._prepare_data(data)

        columns = ', '.join(prepared_data.keys())
        placeholders = ', '.join(['%s'] * len(prepared_data))
        values = tuple(prepared_data.values())

        query = f"""
            INSERT INTO {self.table_name} ({columns})
            VALUES ({placeholders})
            RETURNING *
        """
        record = self._execute_command_return(query, values)
        return self.model_class(**record)

    def create_many(self, data_list: List[Dict[str, Any]]) -> int:
        if not data_list:
            return 0

        # --valida campos de todos los elementos
        for i, data in enumerate(data_list):
            try:
                self._validate_fields(data, f"crear (elemento {i + 1})")
            except ValueError as e:
                raise ValueError(f"Error en elemento {i + 1}: {str(e)}")

        # -- prepara data
        prepared_data_list = self._prepare_data_list(data_list)

        columns = list(prepared_data_list[0].keys())
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))

        # -- usa execute_values para mejor rendimiento con muchos registros
        # -- solo se usa cuando se crean muchos, mejor para el cold start
        from psycopg2.extras import execute_values

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                values_list = [tuple(data[col] for col in columns) for data in prepared_data_list]

                query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES %s"
                execute_values(cursor, query, values_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise

    def update(self, id: str, data: Dict[str, Any]) -> Optional[T]:
        if not data:
            raise ValueError("No se proporcionaron datos para actualizar")

        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        # Validar campos con el modelo (excluyendo 'id' opcional)
        self._validate_attributes(data, "update", exclude_id=True)

        # Convertir datos automáticamente
        prepared_data = self._prepare_data(data)

        set_clause = ', '.join([f"{key} = %s" for key in prepared_data.keys()])
        values = tuple(prepared_data.values()) + (id,)

        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE id = %s
            RETURNING *
        """
        record = self._execute_command_return(query, values)
        return self.model_class(**record) if record else None

    def delete(self, id: str) -> bool:
        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        query = f"DELETE FROM {self.table_name} WHERE id = %s"
        row_count = self._execute_command(query, (id,))
        return row_count == 1

    def exists_by_id(self, id: str) -> bool:
        """Verifica si existe un registro con el ID dado."""
        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        query = f"SELECT 1 FROM {self.table_name} WHERE id = %s LIMIT 1"
        record = self._execute_query_one(query, (id,))
        return record is not None

    def find_by_attribute(
            self,
            attribute: str,
            value: Any,
            limit: int = 100,
            offset: int = 0,
            order_by: Optional[Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]]] = None
    ) -> List[T]:
        """
        Busca por un atributo (soporta valores exactos o listas tipo IN).

        Args:
            attribute: Nombre del atributo a buscar
            value: Valor o lista de valores a buscar
            limit: Límite de resultados
            offset: Desplazamiento para paginación
            order_by: Ordenamiento. Puede ser:
                - str: "nombre" (ASC por defecto)
                - Tuple: ("nombre", "ASC")
                - List[str]: ["nombre", "fecha"] (ASC por defecto)
                - List[Tuple[str, str]]: [("nombre", "ASC"), ("fecha", "DESC")]
        """
        self._validate_attributes(attribute, "find_by_attribute")

        if limit < 0 or offset < 0:
            raise ValueError("Limit y offset deben ser >= 0")

        # Validar y construir ORDER BY
        order_clause = self._build_order_clause(order_by)

        # Prepara valores
        converted_value = self._convert_value_for_sql(value)
        if isinstance(value, (list, tuple, set)):
            converted_values = [self._convert_value_for_sql(v) for v in value]
            placeholders = ', '.join(['%s'] * len(converted_values))
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE {attribute} IN ({placeholders})
                {order_clause}
                LIMIT %s OFFSET %s
            """
            params = tuple(converted_values) + (limit, offset)
        else:
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE {attribute} = %s
                {order_clause}
                LIMIT %s OFFSET %s
            """
            params = (converted_value, limit, offset)

        records = self._execute_query(query, params)
        return [self.model_class(**r) for r in records]

    def find_by_attributes(
            self,
            filters: Dict[str, Any],
            limit: int = 100,
            offset: int = 0,
            order_by: Optional[Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]]] = None
    ) -> List[T]:
        """
        Busca por múltiples atributos (soporta '=' o 'IN' si el valor es lista/tupla).

        Args:
            filters: Diccionario de filtros {atributo: valor}
            limit: Límite de resultados
            offset: Desplazamiento para paginación
            order_by: Ordenamiento. Puede ser:
                - str: "nombre" (ASC por defecto)
                - Tuple: ("nombre", "ASC")
                - List[str]: ["nombre", "fecha"] (ASC por defecto)
                - List[Tuple[str, str]]: [("nombre", "ASC"), ("fecha", "DESC")]
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro")

        self._validate_attributes(filters, "find_by_attributes")

        # --valida y construye ORDER BY
        order_clause = self._build_order_clause(order_by)

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        values.extend([limit, offset])
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE {' AND '.join(where_clauses)}
            {order_clause}
            LIMIT %s OFFSET %s
        """

        records = self._execute_query(query, tuple(values))
        return [self.model_class(**r) for r in records]

    def conditional_create(self, data: Dict[str, Any], condition_field: str, condition_value: Any) -> Optional[Any]:
        """Crear solo si no existe registro que cumpla condición"""
        # valida campos del data
        self._validate_fields(data, "crear condicionalmente")

        # valida que el campo de condición existe en el modelo usando la función centralizada
        self._validate_attributes(condition_field, "conditional_create - campo de condición")

        converted_condition = self._convert_value_for_sql(condition_value)
        check_query = f"SELECT 1 FROM {self.table_name} WHERE {condition_field} = %s LIMIT 1"

        exists = self._execute_query_one(check_query, (converted_condition,))

        if exists:
            return None

        return self.create(data)

    def upsert(self, data: Dict[str, Any], conflict_columns: List[str]) -> Any:
        """Insert o Update si ya existe (PostgreSQL UPSERT)"""
        # valida campos del data
        self._validate_fields(data, "upsert")

        # valida que las columnas de conflicto existen en el modelo usando la función centralizada
        self._validate_attributes(conflict_columns, "upsert - columnas de conflicto")

        if not conflict_columns:
            raise ValueError("conflict_columns no puede estar vacío")

        prepared_data = self._prepare_data(data)

        columns = ', '.join(prepared_data.keys())
        placeholders = ', '.join(['%s'] * len(prepared_data))
        values = tuple(prepared_data.values())

        conflict_cols = ', '.join(conflict_columns)
        update_clauses = [f"{k} = EXCLUDED.{k}" for k in prepared_data.keys() if k not in conflict_columns]

        query = f"""
            INSERT INTO {self.table_name} ({columns})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols})
            DO UPDATE SET {', '.join(update_clauses)}
            RETURNING *
        """
        record = self._execute_command_return(query, values)
        return self.model_class(**record)

    def upsert_many(self, data_list: List[Dict[str, Any]], conflict_columns: List[str]) -> int:
        """
        Batch upsert para múltiples registros (PostgreSQL ON CONFLICT)

        Args:
            data_list: Lista de diccionarios con datos a insertar/actualizar
            conflict_columns: Columnas que definen el conflicto para el upsert

        Returns:
            int: Número de registros afectados
        """
        if not data_list:
            return 0

        if not conflict_columns:
            raise ValueError("conflict_columns no puede estar vacío")

        # Validar campos de todos los elementos
        for i, data in enumerate(data_list):
            try:
                self._validate_fields(data, f"upsert (elemento {i + 1})")
            except ValueError as e:
                raise ValueError(f"Error en elemento {i + 1}: {str(e)}")

        # Validar que las columnas de conflicto existen en el modelo usando la función centralizada
        self._validate_attributes(conflict_columns, "upsert_many - columnas de conflicto")

        # Preparar datos
        prepared_data_list = self._prepare_data_list(data_list)

        columns = list(prepared_data_list[0].keys())
        columns_str = ', '.join(columns)

        conflict_cols = ', '.join(conflict_columns)
        update_clauses = [f"{k} = EXCLUDED.{k}" for k in columns if k not in conflict_columns]

        if not update_clauses:
            # Si todas las columnas son de conflicto, no hay nada que actualizar
            update_clause = "DO NOTHING"
        else:
            update_clause = f"DO UPDATE SET {', '.join(update_clauses)}"

        #-solo si se lo requiere
        # ssar execute_values para mejor rendimiento
        from psycopg2.extras import execute_values

        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                values_list = [tuple(data[col] for col in columns) for data in prepared_data_list]

                query = f"""
                    INSERT INTO {self.table_name} ({columns_str}) VALUES %s
                    ON CONFLICT ({conflict_cols})
                    {update_clause}
                """
                execute_values(cursor, query, values_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            conn.rollback()
            raise

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Cuenta registros, opcionalmente con filtros

        Args:
            filters: Diccionario de filtros opcional {atributo: valor}

        Returns:
            int: Número de registros que cumplen los filtros
        """
        if filters is None:
            query = f"SELECT COUNT(*) as count FROM {self.table_name}"
            params = None
        else:
            if not filters:
                raise ValueError("Si proporciona filtros, no pueden estar vacíos")

            # Usar la función centralizada de validación
            self._validate_attributes(filters, "count - filtros")

            where_clauses = []
            values = []
            for attr, val in filters.items():
                converted_val = self._convert_value_for_sql(val)
                if isinstance(val, (list, tuple, set)):
                    if not val:
                        raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                    converted_vals = [self._convert_value_for_sql(v) for v in val]
                    placeholders = ', '.join(['%s'] * len(converted_vals))
                    where_clauses.append(f"{attr} IN ({placeholders})")
                    values.extend(converted_vals)
                else:
                    where_clauses.append(f"{attr} = %s")
                    values.append(converted_val)

            query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE {' AND '.join(where_clauses)}"
            params = tuple(values)

        record = self._execute_query_one(query, params)
        return record['count'] if record else 0

    def exists_by_attributes(self, filters: Dict[str, Any]) -> bool:
        """
        Verifica si existe al menos un registro que cumpla los filtros

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            bool: True si existe al menos un registro
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro")

        # Usar la función centralizada de validación
        self._validate_attributes(filters, "exists_by_attributes - filtros")

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        query = f"SELECT 1 FROM {self.table_name} WHERE {' AND '.join(where_clauses)} LIMIT 1"
        record = self._execute_query_one(query, tuple(values))
        return record is not None

    def delete_by_attributes(self, filters: Dict[str, Any]) -> int:
        """
        Elimina registros que cumplan los filtros

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            int: Número de registros eliminados
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro para evitar eliminación accidental de toda la tabla")

        # Usar la función centralizada de validación
        self._validate_attributes(filters, "delete_by_attributes - filtros")

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        query = f"DELETE FROM {self.table_name} WHERE {' AND '.join(where_clauses)}"
        return self._execute_command(query, tuple(values))

    def find_one_by_attributes(self, filters: Dict[str, Any]) -> Optional[T]:
        """
        Busca un único registro por filtros (devuelve el primero si hay múltiples)

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            Optional[T]: El primer registro encontrado o None
        """
        results = self.find_by_attributes(filters, limit=1, offset=0)
        return results[0] if results else None

    def bulk_update_by_attributes(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """
        Actualización masiva con filtros personalizados (versión no transaccional)

        Args:
            filters: Diccionario de filtros {atributo: valor}
            updates: Diccionario de actualizaciones {atributo: nuevo_valor}

        Returns:
            int: Número de registros actualizados
        """
        if not filters or not updates:
            raise ValueError("Filters y updates no pueden estar vacíos")

        # Validar campos de filtros usando la función centralizada
        self._validate_attributes(filters, "bulk_update_by_attributes - filtros")

        # Validar campos de actualizaciones usando la función centralizada (excluyendo ID)
        self._validate_attributes(updates, "bulk_update_by_attributes - actualizaciones", exclude_id=True)

        # Validar que no se actualice el ID (verificación adicional)
        if 'id' in updates:
            raise ValueError("No se permite actualizar el campo 'id' en bulk_update_by_attributes")

        # Preparar filtros
        prepared_filters = self._prepare_data(filters)
        where_clauses = []
        where_values = []
        for attr, val in prepared_filters.items():
            if isinstance(filters[attr], (list, tuple, set)):  # Usar original para check
                converted_vals = [self._convert_value_for_sql(v) for v in filters[attr]]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                where_values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                where_values.append(val)

        # Preparar updates
        prepared_updates = self._prepare_data(updates)
        set_clauses = [f"{key} = %s" for key in prepared_updates.keys()]
        set_values = list(prepared_updates.values())

        query = f"""
            UPDATE {self.table_name}
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(where_clauses)}
        """

        all_values = tuple(set_values + where_values)
        return self._execute_command(query, all_values)


class TransactionContext:
    """Contexto de transacción que envuelve operaciones sin auto-commit"""

    def __init__(self, repository: BaseRepository, connection):
        self.repo = repository
        self.conn = connection

    def _validate_fields(self, data: Dict[str, Any], operation: str = "operación") -> None:
        """Valida que los campos estén en el modelo usando la función del repositorio"""
        if not data:
            raise ValueError(f"No se proporcionaron datos para {operation}")

        # Usar la función de validación del repositorio
        self.repo._validate_attributes(data, operation)

    def create(self, data: Dict[str, Any]) -> Any:
        """Crear registro dentro de transacción"""
        # valida campos con el modelo
        self._validate_fields(data, "crear")

        # -- prepara data para sql
        prepared_data = self.repo._prepare_data(data)

        columns = ', '.join(prepared_data.keys())
        placeholders = ', '.join(['%s'] * len(prepared_data))
        values = tuple(prepared_data.values())

        query = f"""
            INSERT INTO {self.repo.table_name} ({columns})
            VALUES ({placeholders})
            RETURNING *
        """
        record = self.repo._execute_command_return_with_conn(self.conn, query, values)
        return self.repo.model_class(**record)

    def update(self, id: str, data: Dict[str, Any]) -> Optional[Any]:
        """Actualizar registro dentro de transacción"""
        if not data:
            raise ValueError("No se proporcionaron datos para actualizar")

        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        # Validar campos con el modelo (excluyendo 'id' opcional) usando la función del repositorio
        self.repo._validate_attributes(data, "actualización", exclude_id=True)

        # -- prepara data para sql con la funcion del repo
        prepared_data = self.repo._prepare_data(data)

        set_clause = ', '.join([f"{key} = %s" for key in prepared_data.keys()])
        values = tuple(prepared_data.values()) + (id,)

        query = f"""
            UPDATE {self.repo.table_name}
            SET {set_clause}
            WHERE id = %s
            RETURNING *
        """
        record = self.repo._execute_command_return_with_conn(self.conn, query, values)
        return self.repo.model_class(**record) if record else None

    def delete(self, id: str) -> bool:
        """Eliminar registro dentro de transacción"""
        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        query = f"DELETE FROM {self.repo.table_name} WHERE id = %s"
        row_count = self.repo._execute_command_with_conn(self.conn, query, (id,))
        return row_count == 1

    def create_many(self, data_list: List[Dict[str, Any]]) -> int:
        """Crear múltiples registros dentro de transacción"""
        if not data_list:
            return 0

        # valida campos de todos los elementos
        for i, data in enumerate(data_list):
            try:
                self._validate_fields(data, f"crear (elemento {i + 1})")
            except ValueError as e:
                raise ValueError(f"Error en elemento {i + 1}: {str(e)}")

        # -- prepara data para sql con la funcion del repo
        prepared_data_list = self.repo._prepare_data_list(data_list)

        columns = list(prepared_data_list[0].keys())
        columns_str = ', '.join(columns)

        # -- usa execute_values para mejorar rendimiento
        # -- solo se usa cuando se crean muchos, mejor para el cold start
        from psycopg2.extras import execute_values

        with self.conn.cursor() as cursor:
            values_list = [tuple(data[col] for col in columns) for data in prepared_data_list]
            query = f"INSERT INTO {self.repo.table_name} ({columns_str}) VALUES %s"
            execute_values(cursor, query, values_list)
            return cursor.rowcount

    def execute_raw_query(self, query: str, params: tuple = None) -> List[dict]:
        """
        Ejecutar consulta SQL cruda dentro de transacción
        SOLO usar con queries controlados internamente, NUNCA con input del usuario
        """
        query_upper = query.strip().upper()
        if not query_upper.startswith('SELECT'):
            raise ValueError("execute_raw_query solo permite consultas SELECT")

        dangerous_patterns = [';--', '/*', '*/', 'xp_', 'sp_']
        for pattern in dangerous_patterns:
            if pattern in query.lower():
                raise ValueError(f"Query contiene patrón peligroso: {pattern}")

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_raw_command(self, query: str, params: tuple = None) -> int:
        """
        Ejecutar comando SQL crudo dentro de transacción
        SOLO usar internamente con queries pre-validados
        """
        query_upper = query.strip().upper()
        allowed_commands = ['INSERT', 'UPDATE', 'DELETE']

        if not any(query_upper.startswith(cmd) for cmd in allowed_commands):
            raise ValueError(f"execute_raw_command solo permite: {', '.join(allowed_commands)}")

        dangerous_patterns = [';--', '/*', '*/', 'drop ', 'truncate ', 'alter ', 'create ']
        for pattern in dangerous_patterns:
            if pattern in query.lower():
                raise ValueError(f"Query contiene patrón bloqueado: {pattern}")

        with self.conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def bulk_update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Actualización masiva con filtros personalizados"""
        if not filters or not updates:
            raise ValueError("Filters and updates cannot be empty")

        # Validar campos de filtros usando la función del repositorio
        self.repo._validate_attributes(filters, "bulk_update - filtros")

        # Validar campos de actualizaciones usando la función del repositorio (excluyendo ID)
        self.repo._validate_attributes(updates, "bulk_update - actualizaciones", exclude_id=True)

        # Validar que no se actualice el ID (verificación adicional)
        if 'id' in updates:
            raise ValueError("No se permite actualizar el campo 'id' en bulk_update")

        # prepara filtros
        prepared_filters = self.repo._prepare_data(filters)
        where_clauses = []
        where_values = []
        for attr, val in prepared_filters.items():
            if isinstance(filters[attr], (list, tuple, set)):  # Usar original para check
                converted_vals = [self.repo._convert_value_for_sql(v) for v in filters[attr]]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                where_values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                where_values.append(val)

        # preparar updates
        prepared_updates = self.repo._prepare_data(updates)
        set_clauses = [f"{key} = %s" for key in prepared_updates.keys()]
        set_values = list(prepared_updates.values())

        query = f"""
            UPDATE {self.repo.table_name}
            SET {', '.join(set_clauses)}
            WHERE {' AND '.join(where_clauses)}
        """

        all_values = tuple(set_values + where_values)
        return self.repo._execute_command_with_conn(self.conn, query, all_values)

    def conditional_create(self, data: Dict[str, Any], condition_field: str, condition_value: Any) -> Optional[Any]:
        """Crear solo si no existe registro que cumpla condición"""
        # valida campos del data
        self._validate_fields(data, "crear condicionalmente")

        # valida que el campo de condición existe en el modelo usando la función del repositorio
        self.repo._validate_attributes(condition_field, "conditional_create - campo de condición")

        converted_condition = self.repo._convert_value_for_sql(condition_value)
        check_query = f"SELECT 1 FROM {self.repo.table_name} WHERE {condition_field} = %s LIMIT 1"

        with self.conn.cursor() as cursor:
            cursor.execute(check_query, (converted_condition,))
            exists = cursor.fetchone()

        if exists:
            return None

        return self.create(data)

    def upsert(self, data: Dict[str, Any], conflict_columns: List[str]) -> Any:
        """Insert o Update si ya existe (PostgreSQL UPSERT)"""
        # valida campos del data
        self._validate_fields(data, "upsert")

        # valida que las columnas de conflicto existen en el modelo usando la función del repositorio
        self.repo._validate_attributes(conflict_columns, "upsert - columnas de conflicto")

        if not conflict_columns:
            raise ValueError("conflict_columns no puede estar vacío")

        prepared_data = self.repo._prepare_data(data)

        columns = ', '.join(prepared_data.keys())
        placeholders = ', '.join(['%s'] * len(prepared_data))
        values = tuple(prepared_data.values())

        conflict_cols = ', '.join(conflict_columns)
        update_clauses = [f"{k} = EXCLUDED.{k}" for k in prepared_data.keys() if k not in conflict_columns]

        query = f"""
            INSERT INTO {self.repo.table_name} ({columns})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_cols})
            DO UPDATE SET {', '.join(update_clauses)}
            RETURNING *
        """
        record = self.repo._execute_command_return_with_conn(self.conn, query, values)
        return self.repo.model_class(**record)

    def upsert_many(self, data_list: List[Dict[str, Any]], conflict_columns: List[str]) -> int:
        """
        Batch upsert para múltiples registros dentro de transacción

        Args:
            data_list: Lista de diccionarios con datos a insertar/actualizar
            conflict_columns: Columnas que definen el conflicto para el upsert

        Returns:
            int: Número de registros afectados
        """
        if not data_list:
            return 0

        if not conflict_columns:
            raise ValueError("conflict_columns no puede estar vacío")

        # Validar campos de todos los elementos
        for i, data in enumerate(data_list):
            try:
                self._validate_fields(data, f"upsert (elemento {i + 1})")
            except ValueError as e:
                raise ValueError(f"Error en elemento {i + 1}: {str(e)}")

        # Validar que las columnas de conflicto existen en el modelo usando la función del repositorio
        self.repo._validate_attributes(conflict_columns, "upsert_many - columnas de conflicto")

        # Preparar datos
        prepared_data_list = self.repo._prepare_data_list(data_list)

        columns = list(prepared_data_list[0].keys())
        columns_str = ', '.join(columns)

        conflict_cols = ', '.join(conflict_columns)
        update_clauses = [f"{k} = EXCLUDED.{k}" for k in columns if k not in conflict_columns]

        if not update_clauses:
            # Si todas las columnas son de conflicto, no hay nada que actualizar
            update_clause = "DO NOTHING"
        else:
            update_clause = f"DO UPDATE SET {', '.join(update_clauses)}"

        # Usar execute_values para mejor rendimiento
        from psycopg2.extras import execute_values

        with self.conn.cursor() as cursor:
            values_list = [tuple(data[col] for col in columns) for data in prepared_data_list]

            query = f"""
                INSERT INTO {self.repo.table_name} ({columns_str}) VALUES %s
                ON CONFLICT ({conflict_cols})
                {update_clause}
            """
            execute_values(cursor, query, values_list)
            return cursor.rowcount

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Cuenta registros dentro de transacción, opcionalmente con filtros

        Args:
            filters: Diccionario de filtros opcional {atributo: valor}

        Returns:
            int: Número de registros que cumplen los filtros
        """
        if filters is None:
            query = f"SELECT COUNT(*) as count FROM {self.repo.table_name}"
            params = None
        else:
            if not filters:
                raise ValueError("Si proporciona filtros, no pueden estar vacíos")

            # Usar la función centralizada de validación del repositorio
            self.repo._validate_attributes(filters, "count - filtros")

            where_clauses = []
            values = []
            for attr, val in filters.items():
                converted_val = self.repo._convert_value_for_sql(val)
                if isinstance(val, (list, tuple, set)):
                    if not val:
                        raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                    converted_vals = [self.repo._convert_value_for_sql(v) for v in val]
                    placeholders = ', '.join(['%s'] * len(converted_vals))
                    where_clauses.append(f"{attr} IN ({placeholders})")
                    values.extend(converted_vals)
                else:
                    where_clauses.append(f"{attr} = %s")
                    values.append(converted_val)

            query = f"SELECT COUNT(*) as count FROM {self.repo.table_name} WHERE {' AND '.join(where_clauses)}"
            params = tuple(values)

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            record = cursor.fetchone()
            return record['count'] if record else 0

    def exists_by_attributes(self, filters: Dict[str, Any]) -> bool:
        """
        Verifica si existe al menos un registro que cumpla los filtros dentro de transacción

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            bool: True si existe al menos un registro
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro")

        # Usar la función centralizada de validación del repositorio
        self.repo._validate_attributes(filters, "exists_by_attributes - filtros")

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self.repo._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self.repo._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        query = f"SELECT 1 FROM {self.repo.table_name} WHERE {' AND '.join(where_clauses)} LIMIT 1"

        with self.conn.cursor() as cursor:
            cursor.execute(query, tuple(values))
            record = cursor.fetchone()
            return record is not None

    def delete_by_attributes(self, filters: Dict[str, Any]) -> int:
        """
        Elimina registros que cumplan los filtros dentro de transacción

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            int: Número de registros eliminados
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro para evitar eliminación accidental de toda la tabla")

        # Usar la función centralizada de validación del repositorio
        self.repo._validate_attributes(filters, "delete_by_attributes - filtros")

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self.repo._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self.repo._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        query = f"DELETE FROM {self.repo.table_name} WHERE {' AND '.join(where_clauses)}"
        return self.repo._execute_command_with_conn(self.conn, query, tuple(values))

    def delete_by_statement_and_period_account_type_pairs(
        self,
        financial_statement_id: str,
        period_account_type_pairs: List[Tuple[str, str]],
    ) -> int:
        """
        Solo FinancialDatapointRepository: DELETE con JOIN a accounts (confirm_draft opción A).
        """
        fn = getattr(self.repo, "delete_by_statement_and_period_account_type_pairs_with_conn", None)
        if fn is None:
            raise AttributeError(
                f"{type(self.repo).__name__} no implementa delete_by_statement_and_period_account_type_pairs_with_conn"
            )
        return fn(self.conn, financial_statement_id, period_account_type_pairs)

    def get_distinct_years_and_periods(self, statement_id: str) -> Dict[str, List]:
        """
        Solo FinancialDatapointRepository: años/periodos distintos en la transacción actual.
        """
        fn = getattr(self.repo, "get_distinct_years_and_periods_with_conn", None)
        if fn is None:
            raise AttributeError(
                f"{type(self.repo).__name__} no implementa get_distinct_years_and_periods_with_conn"
            )
        return fn(self.conn, statement_id)

    def find_by_attributes(
            self,
            filters: Dict[str, Any],
            limit: int = 100,
            offset: int = 0,
            order_by: Optional[Union[str, Tuple[str, str], List[str], List[Tuple[str, str]]]] = None
    ) -> List[Any]:
        """
        Busca registros por múltiples atributos dentro de transacción

        Args:
            filters: Diccionario de filtros {atributo: valor}
            limit: Límite de resultados
            offset: Desplazamiento para paginación
            order_by: Ordenamiento (igual que en BaseRepository)

        Returns:
            List[T]: Lista de registros que cumplen los filtros
        """
        if not filters:
            raise ValueError("Debe proporcionar al menos un filtro")

        # Usar la función centralizada de validación del repositorio
        self.repo._validate_attributes(filters, "find_by_attributes - filtros")

        if limit < 0 or offset < 0:
            raise ValueError("Limit y offset deben ser >= 0")

        # Validar y construir ORDER BY
        order_clause = self.repo._build_order_clause(order_by)

        where_clauses = []
        values = []
        for attr, val in filters.items():
            converted_val = self.repo._convert_value_for_sql(val)
            if isinstance(val, (list, tuple, set)):
                if not val:
                    raise ValueError(f"El filtro para '{attr}' no puede ser una lista vacía")
                converted_vals = [self.repo._convert_value_for_sql(v) for v in val]
                placeholders = ', '.join(['%s'] * len(converted_vals))
                where_clauses.append(f"{attr} IN ({placeholders})")
                values.extend(converted_vals)
            else:
                where_clauses.append(f"{attr} = %s")
                values.append(converted_val)

        values.extend([limit, offset])
        query = f"""
            SELECT * FROM {self.repo.table_name}
            WHERE {' AND '.join(where_clauses)}
            {order_clause}
            LIMIT %s OFFSET %s
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, tuple(values))
            records = cursor.fetchall()
            return [self.repo.model_class(**r) for r in records]

    def find_one_by_attributes(self, filters: Dict[str, Any]) -> Optional[Any]:
        """
        Busca un único registro por filtros dentro de transacción

        Args:
            filters: Diccionario de filtros {atributo: valor}

        Returns:
            Optional[T]: El primer registro encontrado o None
        """
        results = self.find_by_attributes(filters, limit=1, offset=0)
        return results[0] if results else None

    #agregue metodo para buscar por id
    def find_by_id(self, id: str) -> Optional[Any]:
        """Busca un registro por ID dentro de transacción"""
        if not id or not str(id).strip():
            raise ValueError("ID no puede estar vacío")

        query = f"SELECT * FROM {self.repo.table_name} WHERE id = %s"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (id,))
            record = cursor.fetchone()
            return self.repo.model_class(**record) if record else None


class TransactionManager:
    """Manager para transacciones que abarcan múltiples repositorios"""

    def __init__(self, *repositories):
        if not repositories:
            raise ValueError("TransactionManager requiere al menos un repositorio")

        self.repositories = repositories

    def _get_connection(self):
        """Obtiene la conexión singleton directamente"""
        return DatabaseSingletonConnection.get_connection()

    @contextmanager
    def transaction(self):
        """
        Context manager para transacciones multi-repositorio.
        Uso: with TransactionManager(repo1, repo2).transaction() as tx_repos:
                 tx_repos['users'].create(data1)
                 tx_repos['evaluators'].create(data2)
        """
        conn = self._get_connection()
        try:
            tx_contexts = {}
            for repo in self.repositories:
                tx_contexts[repo.table_name] = TransactionContext(repo, conn)

            yield tx_contexts
            conn.commit()
        except Exception:
            conn.rollback()
            raise