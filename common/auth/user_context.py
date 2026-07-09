import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _normalize_role(role: str) -> Optional[str]:
    if role is None:
        return None
    cleaned = str(role).strip().upper()
    return cleaned or None


def parse_roles_from_claims(claims: Dict[str, Any]) -> List[str]:
    """
    Extrae roles desde Cognito/API Gateway.
    Orden: cognito:groups → custom:role → claim role.
    """
    roles: List[str] = []
    seen = set()

    def add(role: Optional[str]) -> None:
        normalized = _normalize_role(role)
        if normalized and normalized not in seen:
            seen.add(normalized)
            roles.append(normalized)

    raw_groups = claims.get("cognito:groups")
    if raw_groups is not None:
        if isinstance(raw_groups, list):
            for g in raw_groups:
                add(g)
        elif isinstance(raw_groups, str):
            text = raw_groups.strip()
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        for g in parsed:
                            add(g)
                except json.JSONDecodeError:
                    pass
            if not roles:
                for part in text.replace("[", "").replace("]", "").split(","):
                    add(part)

    add(claims.get("custom:role"))
    add(claims.get("role"))

    return roles


def parse_evaluator_id_from_claims(claims: Dict[str, Any]) -> Optional[str]:
    """Tenant/evaluator desde claims custom (organization_id o evaluator_id legacy)."""
    for key in ("custom:organization_id", "custom:evaluator_id"):
        value = claims.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    # API Gateway a veces expone custom attrs con otro prefijo en el claim name
    for claim_key, value in claims.items():
        if value is None or not str(value).strip():
            continue
        lowered = claim_key.lower()
        if "organization_id" in lowered or lowered.endswith("evaluator_id"):
            return str(value).strip()

    return None


def _find_db_user(repo, sub: Optional[str], email: Optional[str]):
    if sub:
        db_user = repo.find_by_id(str(sub))
        if db_user:
            return db_user
    if email:
        matches = repo.find_by_attribute("email", str(email).strip().lower(), limit=1)
        if not matches:
            matches = repo.find_by_attribute("email", str(email).strip(), limit=1)
        if matches:
            return matches[0]
    return None


def enrich_evaluator_regulatory(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adjunta país y reglas regulatorias del tenant (evaluator) al usuario autenticado.
    El front usa estos campos para monedas, tax id y defaults sin hardcodear por ambiente.
    """
    evaluator_id = user.get("evaluator_id")
    if not evaluator_id or not str(evaluator_id).strip():
        return user

    try:
        from common.regulatory.context import RegulatoryContext
        from common.regulatory.exceptions import UnknownCountryError

        ctx = RegulatoryContext.for_evaluator(str(evaluator_id).strip())
        profile = ctx.profile
        user["evaluator_country"] = ctx.country
        user["allowed_currencies"] = sorted(profile.allowed_currencies)
        user["default_currency"] = profile.default_currency
        user["tax_id_label"] = profile.tax_id_label
        user["default_scale_type"] = profile.default_scale_type
        logger.info(
            "Regulatory context evaluator_id=%s country=%s currencies=%s",
            evaluator_id,
            ctx.country,
            user["allowed_currencies"],
        )
    except UnknownCountryError as err:
        logger.warning(
            "Sin contexto regulatorio para evaluator_id=%s: %s",
            evaluator_id,
            err,
        )
    except Exception as err:
        logger.warning(
            "No se pudo enriquecer regulatory context evaluator_id=%s: %s",
            evaluator_id,
            err,
            exc_info=True,
        )

    return user


def enrich_user_from_database(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Completa roles y evaluator_id desde tabla users.
    Siempre fusiona users.role (no solo cuando el token no trae grupos):
    Cognito puede tener un grupo distinto (USER/ANALYST) y la BD el rol real ADMIN.
    """
    sub = user.get("sub")
    email = user.get("email")
    if sub or email:
        try:
            from common.models.models import User
            from common.repositories.base import BaseRepository

            repo = BaseRepository("users", User)
            db_user = _find_db_user(repo, sub, email)
            if not db_user:
                logger.warning(
                    "Sin fila en users para enriquecer (sub=%s email=%s)",
                    sub,
                    email,
                )
            else:
                role = _normalize_role(db_user.role)
                if role:
                    existing = list(user.get("roles") or [])
                    if role not in existing:
                        user["roles"] = existing + [role]

                if not user.get("evaluator_id") and db_user.evaluator_id:
                    user["evaluator_id"] = str(db_user.evaluator_id)

                logger.info(
                    "Usuario enriquecido desde BD user_id=%s roles=%s evaluator_id=%s",
                    db_user.id,
                    user.get("roles"),
                    user.get("evaluator_id"),
                )
        except Exception as err:
            logger.warning("No se pudo enriquecer usuario desde BD: %s", err, exc_info=True)

    return enrich_evaluator_regulatory(user)


def build_current_user_payload(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Payload HTTP para GET /users/me: perfil + contexto regulatorio del tenant.
    user debe venir de enrich_user_from_database (event['user']).
    """
    payload: Dict[str, Any] = {
        "id": user.get("sub"),
        "sub": user.get("sub"),
        "name": user.get("name"),
        "email": user.get("email"),
        "roles": list(user.get("roles") or []),
        "evaluator_id": user.get("evaluator_id"),
        "evaluator_country": user.get("evaluator_country"),
        "allowed_currencies": user.get("allowed_currencies"),
        "default_currency": user.get("default_currency"),
        "tax_id_label": user.get("tax_id_label"),
        "default_scale_type": user.get("default_scale_type"),
    }

    sub = user.get("sub")
    if sub:
        try:
            from common.models.models import User
            from common.repositories.base import BaseRepository

            db_user = BaseRepository("users", User).find_by_id(str(sub))
            if db_user:
                if db_user.name:
                    payload["name"] = db_user.name
                if db_user.phone_number:
                    payload["phone_number"] = db_user.phone_number
                if db_user.dni:
                    payload["dni"] = db_user.dni
                if db_user.role:
                    payload["role"] = _normalize_role(db_user.role)
        except Exception as err:
            logger.warning("No se pudo completar perfil BD para /users/me sub=%s: %s", sub, err)

    if not payload.get("role") and payload.get("roles"):
        payload["role"] = payload["roles"][-1]

    return {k: v for k, v in payload.items() if v is not None}
