"""
LLM SQL Copilot engine.

Pipeline:
1. Detect whether the message is conversation or data-related.
2. For data questions, select relevant tables from table descriptions.
3. Fetch only those real SQLite schemas.
4. Generate, validate, and execute one read-only SELECT query.
5. Explain only the returned database evidence.
"""
from __future__ import annotations

import json
import re
import time
import asyncio
from difflib import SequenceMatcher
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, Set, Tuple

import httpx
from loguru import logger
from openai import AsyncAzureOpenAI, AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from .copilot_prompts import (
    CONVERSATION_PROMPT,
    INTENT_DETECTION_PROMPT,
    NARRATION_PROMPT,
    QUERY_PLANNING_PROMPT,
    SQL_GENERATION_PROMPT,
    SQL_REPAIR_PROMPT,
    TABLE_EXPANSION_PROMPT,
    TABLE_SELECTION_PROMPT,
)
from .copilot_few_shots import matching_few_shots
from .table_description import TABLE_DESCRIPTIONS, TABLE_RELATIONSHIPS


MAX_SELECTED_TABLES = 8
MAX_RESULT_ROWS = 100
_LLM_UNAVAILABLE_UNTIL = 0.0
LLM_REQUEST_TIMEOUT_SECONDS = 18.0
LLM_COOLDOWN_SECONDS = 5.0


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _json_object(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _truncate(value: Any, max_chars: int = 24000) -> str:
    payload = json.dumps(value, indent=2, default=str)
    return payload if len(payload) <= max_chars else payload[:max_chars] + "\n... [truncated]"


async def _call_model(system_prompt: str, user_message: str, *, temperature: float = 0.2) -> str:
    """Call the configured LLM provider. Returns an empty string if unavailable."""
    global _LLM_UNAVAILABLE_UNTIL
    if time.monotonic() < _LLM_UNAVAILABLE_UNTIL:
        return ""
    try:
        if settings.llm_provider == "azure_openai" and settings.azure_openai_api_key:
            if (
                "services.ai.azure.com" in settings.azure_openai_endpoint
                or "openai/v1" in settings.azure_openai_endpoint
            ):
                client = AsyncOpenAI(
                    api_key=settings.azure_openai_api_key,
                    base_url=settings.azure_openai_endpoint,
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    http_client=httpx.AsyncClient(trust_env=False),
                )
                response = await asyncio.wait_for(client.chat.completions.create(
                    model=settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=900,
                    temperature=temperature,
                ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            else:
                client = AsyncAzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version=settings.azure_openai_api_version,
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    http_client=httpx.AsyncClient(trust_env=False),
                )
                response = await asyncio.wait_for(client.chat.completions.create(
                    model=settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=900,
                    temperature=temperature,
                ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            return response.choices[0].message.content or ""

        if settings.llm_provider == "openai" and settings.openai_api_key:
            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                http_client=httpx.AsyncClient(trust_env=False),
            )
            response = await asyncio.wait_for(client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=900,
                temperature=temperature,
            ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            return response.choices[0].message.content or ""
    except Exception as exc:
        _LLM_UNAVAILABLE_UNTIL = time.monotonic() + LLM_COOLDOWN_SECONDS
        logger.warning(f"Copilot LLM call failed: {exc}")

    return ""


async def _stream_model(
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.2,
) -> AsyncGenerator[str, None]:
    """Stream text chunks from the configured chat model."""
    global _LLM_UNAVAILABLE_UNTIL
    if time.monotonic() < _LLM_UNAVAILABLE_UNTIL:
        return
    try:
        if settings.llm_provider == "azure_openai" and settings.azure_openai_api_key:
            if (
                "services.ai.azure.com" in settings.azure_openai_endpoint
                or "openai/v1" in settings.azure_openai_endpoint
            ):
                client = AsyncOpenAI(
                    api_key=settings.azure_openai_api_key,
                    base_url=settings.azure_openai_endpoint,
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    http_client=httpx.AsyncClient(trust_env=False),
                )
                stream = await asyncio.wait_for(client.chat.completions.create(
                    model=settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=900,
                    temperature=temperature,
                    stream=True,
                ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            else:
                client = AsyncAzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version=settings.azure_openai_api_version,
                    timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                    http_client=httpx.AsyncClient(trust_env=False),
                )
                stream = await asyncio.wait_for(client.chat.completions.create(
                    model=settings.azure_openai_deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=900,
                    temperature=temperature,
                    stream=True,
                ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            async for chunk in stream:
                token = chunk.choices[0].delta.content if chunk.choices else None
                if token:
                    yield token
            return

        if settings.llm_provider == "openai" and settings.openai_api_key:
            client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=LLM_REQUEST_TIMEOUT_SECONDS,
                http_client=httpx.AsyncClient(trust_env=False),
            )
            stream = await asyncio.wait_for(client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=900,
                temperature=temperature,
                stream=True,
            ), timeout=LLM_REQUEST_TIMEOUT_SECONDS)
            async for chunk in stream:
                token = chunk.choices[0].delta.content if chunk.choices else None
                if token:
                    yield token
            return
    except Exception as exc:
        _LLM_UNAVAILABLE_UNTIL = time.monotonic() + LLM_COOLDOWN_SECONDS
        logger.warning(f"Copilot streaming LLM call failed: {exc}")

    return


def _fallback_intent(query: str) -> str:
    q = _normalize(query)
    if re.search(r"\b(password|passwords|password_hash|secret|secrets|api key|token|tokens)\b", q):
        return "unsupported"
    if re.search(r"^(hi+|he+y+|hell+o+|hello+|thanks?|thank you|ok|okay)\b", q):
        return "conversation"
    if re.search(r"\b(what can you do|help|guide|where can i|how do i)\b", q):
        return "conversation"
    return "data_query"


async def _data_overview(db: AsyncSession) -> str:
    try:
        product_rows = (
            await db.execute(
                text(
                    """
                    SELECT category, COUNT(*) AS sku_count
                    FROM products
                    WHERE category IS NOT NULL
                    GROUP BY category
                    ORDER BY category
                    """
                )
            )
        ).mappings().all()
        categories = ", ".join(f"{row['category']} ({row['sku_count']} SKUs)" for row in product_rows)
        bounds = (
            await db.execute(
                text(
                    """
                    SELECT
                        (SELECT MIN(sale_date) FROM sales) AS first_sale_date,
                        (SELECT MAX(sale_date) FROM sales) AS last_sale_date,
                        (SELECT MIN(forecast_date) FROM sales_forecasts) AS first_forecast_date,
                        (SELECT MAX(forecast_date) FROM sales_forecasts) AS last_forecast_date,
                        (SELECT COUNT(*) FROM warehouses) AS warehouse_count,
                        (SELECT COUNT(*) FROM suppliers) AS supplier_count
                    """
                )
            )
        ).mappings().first()
        if not bounds:
            raise ValueError("No overview rows returned.")
        return (
            f"Catalog categories: {categories or 'none found'}.\n"
            f"Sales data runs from {bounds['first_sale_date']} to {bounds['last_sale_date']}.\n"
            f"Forecast data runs from {bounds['first_forecast_date']} to {bounds['last_forecast_date']}.\n"
            f"The database also covers inventory across {bounds['warehouse_count']} warehouses, suppliers/vendors "
            f"({bounds['supplier_count']} suppliers), returns, shipments, purchase orders, reviews, KPIs, and app users/roles."
        )
    except Exception as exc:
        logger.warning(f"Copilot data overview failed: {exc}")
        return (
            "The database covers products, sales, forecasts, inventory, warehouses, suppliers/vendors, returns, "
            "shipments, purchase orders, reviews, KPIs, and app users/roles."
        )


async def _detect_intent(query: str, db: AsyncSession) -> Dict[str, Any]:
    overview = await _data_overview(db)
    raw = await _call_model(
        INTENT_DETECTION_PROMPT,
        f"User message:\n{query}\n\nData overview:\n{overview}",
        temperature=0.0,
    )
    parsed = _json_object(raw) or {}
    intent = str(parsed.get("intent") or "").strip().lower()
    if intent not in {"conversation", "data_query", "unsupported"}:
        intent = _fallback_intent(query)
    return {
        "intent": intent,
        "reason": parsed.get("reason") or "Local fallback intent detection used.",
        "data_overview": parsed.get("data_overview") or overview,
    }


async def _conversation_answer(query: str) -> str:
    """
    LLM-owned app/help/conversation answer.
    No app-navigation hardcoding here. The CONVERSATION_PROMPT should contain
    app capability/navigation facts.
    """
    response = await _call_model(CONVERSATION_PROMPT, query, temperature=0.3)
    return response or (
        "I can help with app guidance and live business questions about sales, inventory, forecasts, "
        "suppliers, logistics, returns, KPIs, and reports."
    )
    
    
async def _table_schema(db: AsyncSession, table_names: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    schema: Dict[str, List[Dict[str, Any]]] = {}
    for table in table_names:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", table):
            continue
        rows = (await db.execute(text(f"PRAGMA table_info({table})"))).mappings().all()
        if rows:
            schema[table] = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not bool(row["notnull"]),
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ]
    return schema


def _available_table_context() -> Dict[str, Any]:
    return {
        "tables_and_views": TABLE_DESCRIPTIONS,
        "relationships": TABLE_RELATIONSHIPS,
    }


def _important_tokens(value: str) -> Set[str]:
    stopwords = {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from",
        "have", "how", "i", "in", "is", "it", "me", "of", "on", "or", "our", "show",
        "tell", "the", "this", "to", "want", "what", "which", "with", "you",
    }
    return {token for token in _normalize(value).split() if len(token) > 2 and token not in stopwords}


def _fallback_tables(query: str) -> List[str]:
    """Schema-description table scoring used only when the LLM table selector is unavailable."""
    query_tokens = _important_tokens(query)
    scored: List[Tuple[int, str]] = []
    for table, description in TABLE_DESCRIPTIONS.items():
        haystack_tokens = _important_tokens(f"{table} {description}")
        score = len(query_tokens.intersection(haystack_tokens))
        if score:
            scored.append((score, table))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = [table for _score, table in scored[:MAX_SELECTED_TABLES]]
    return selected or list(TABLE_DESCRIPTIONS.keys())[:MAX_SELECTED_TABLES]


def _limit_from_query(query: str, default: int = 50) -> int:
    match = re.search(r"\btop\s+(\d{1,3})\b", _normalize(query))
    if not match:
        return default
    return max(1, min(int(match.group(1)), MAX_RESULT_ROWS))


def _wants_table_output(query: str) -> bool:
    q = _normalize(query)
    table_terms = {
        "list",
        "show",
        "top",
        "bottom",
        "rank",
        "ranking",
        "compare",
        "comparison",
        "which",
        "what",
    }
    return any(term in q.split() for term in table_terms)


async def _select_tables(
    query: str,
    db: AsyncSession,
    *,
    intent_plan: Optional[Dict[str, Any]] = None,
    parent_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LLM-owned table selection.

    This function does not decide business logic with if/else.
    It only provides database context, overview, relationships, and resolved hints.
    The LLM decides the required tables/views.
    """
    overview = str((intent_plan or {}).get("data_overview") or await _data_overview(db))
    hints = await _subject_hints(query, db)

    user_message = f"""
Original user message:
{parent_query or query}

Standalone task/question:
{query}

Detected intent plan:
{json.dumps(intent_plan or {}, indent=2, default=str)}

Data overview:
{overview}

Recognized database hints:
{json.dumps(hints, indent=2, default=str)}

Available database context:
{_truncate(_available_table_context(), max_chars=24000)}

Instructions:
- Select tables/views by reasoning from the business meaning of the standalone task.
- Use table descriptions and relationships.
- Do not generate SQL.
- Do not reject the task here unless no relevant table exists.
- Return only valid JSON.
"""

    raw = await _call_model(TABLE_SELECTION_PROMPT, user_message, temperature=0.0)
    parsed = _json_object(raw) or {}

    tables = parsed.get("tables", [])
    if not isinstance(tables, list):
        tables = []

    selected = [
        table
        for table in tables
        if isinstance(table, str) and table in TABLE_DESCRIPTIONS
    ]

    # Generic operational fallback only if LLM returns invalid/empty output.
    # This is not business hardcoding; it scores table descriptions generically.
    if not selected:
        selected = _fallback_tables(query)

    needs_more = parsed.get("needs_more_if_empty", [])
    if not isinstance(needs_more, list):
        needs_more = []

    needs_more = [
        table
        for table in needs_more
        if isinstance(table, str) and table in TABLE_DESCRIPTIONS
    ]

    return {
        "tables": list(dict.fromkeys(selected))[:MAX_SELECTED_TABLES],
        "reason": parsed.get("reason") or "LLM table selection unavailable; generic schema-description fallback used.",
        "needs_more_if_empty": list(dict.fromkeys(needs_more))[:MAX_SELECTED_TABLES],
    }
    

async def _plan_query(query: str, db: AsyncSession, intent_plan: Dict[str, Any]) -> Dict[str, Any]:
    overview = str(intent_plan.get("data_overview") or await _data_overview(db))
    categories = (await _resolve_catalog_subjects(query, db)).get("available_categories", [])
    user_message = f"""
User message:
{query}

Detected intent:
{json.dumps(intent_plan, indent=2, default=str)}

Data overview:
{overview}

Known catalog categories:
{json.dumps(categories, indent=2)}

Available database context:
{_truncate(_available_table_context(), max_chars=18000)}
"""
    raw = await _call_model(QUERY_PLANNING_PROMPT, user_message, temperature=0.0)
    parsed = _json_object(raw) or {}
    tasks = parsed.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return await _fallback_query_plan(query, db, intent_plan)

    normalized_tasks: List[Dict[str, Any]] = []
    for index, task in enumerate(tasks[:6], start=1):
        if not isinstance(task, dict):
            continue
        task_type = str(task.get("type") or "").strip().lower()
        if task_type not in {"data_query", "conversation", "unsupported"}:
            task_type = "data_query" if _fallback_intent(str(task.get("question") or query)) == "data_query" else "conversation"
        question = str(task.get("question") or query).strip()
        if not question:
            continue
        normalized_tasks.append({
            "id": str(task.get("id") or f"task_{index}"),
            "type": task_type,
            "question": question,
            "recognized_terms": task.get("recognized_terms") if isinstance(task.get("recognized_terms"), list) else [],
            "unsupported_terms": task.get("unsupported_terms") if isinstance(task.get("unsupported_terms"), list) else [],
            "reason": str(task.get("reason") or ""),
        })

    if not normalized_tasks:
        return await _fallback_query_plan(query, db, intent_plan)
    return {
        "intent": parsed.get("intent") or intent_plan.get("intent") or "data_query",
        "reason": parsed.get("reason") or "LLM query plan created.",
        "tasks": normalized_tasks,
    }


async def _fallback_query_plan(query: str, db: AsyncSession, intent_plan: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(intent_plan.get("intent") or _fallback_intent(query))
    if intent != "data_query":
        return {
            "intent": intent,
            "reason": intent_plan.get("reason") or "Fallback non-data plan.",
            "tasks": [{"id": "task_1", "type": intent, "question": query, "reason": "Single non-data task."}],
        }
    return {
        "intent": "data_query",
        "reason": "LLM planner unavailable; using the full user message as one data task.",
        "tasks": [{
            "id": "task_1",
            "type": "data_query",
            "question": query,
            "recognized_terms": [],
            "unsupported_terms": [],
            "reason": "Single data task fallback.",
        }],
    }


async def _db_categories(query: str, db: AsyncSession) -> List[str]:
    q = _normalize(query)
    rows = (
        await db.execute(text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL"))
    ).mappings().all()
    matches: List[str] = []
    for row in rows:
        category = str(row.get("category") or "")
        norm = _normalize(category)
        singular = norm[:-1] if norm.endswith("s") else norm
        if norm and (norm in q or singular in q):
            matches.append(category)
    return matches


def _best_match(term: str, choices: Sequence[str], *, threshold: float = 0.82) -> Optional[str]:
    term_norm = _normalize(term)
    best_score = 0.0
    best_choice: Optional[str] = None
    for choice in choices:
        choice_norm = _normalize(choice)
        score = SequenceMatcher(None, term_norm, choice_norm).ratio()
        if score > best_score:
            best_score = score
            best_choice = choice
    return best_choice if best_score >= threshold else None


async def _resolve_catalog_subjects(query: str, db: AsyncSession) -> Dict[str, Any]:
    categories_rows = (
        await db.execute(text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL"))
    ).mappings().all()
    categories = [str(row["category"]) for row in categories_rows]
    resolved: List[str] = []
    query_norm = _normalize(query)
    query_tokens = set(query_norm.split())
    category_lookup = {_normalize(category): category for category in categories}

    for category_norm, category in category_lookup.items():
        singular = category_norm[:-1] if category_norm.endswith("s") else category_norm
        if category_norm in query_norm or singular in query_tokens:
            resolved.append(category)

    if not resolved:
        for token in query_tokens:
            if len(token) < 5:
                continue
            match = _best_match(token, list(category_lookup.keys()), threshold=0.86)
            if match:
                resolved.append(category_lookup[match])

    return {
        "resolved_categories": list(dict.fromkeys(resolved)),
        "unsupported_terms": [],
        "available_categories": categories,
    }


async def _find_product(query: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    query_norm = f" {_normalize(query)} "
    rows = (
        await db.execute(
            text(
                """
                SELECT product_id, product_name, sku, product_code, brand, category
                FROM products
                """
            )
        )
    ).mappings().all()

    best: Optional[Tuple[int, Dict[str, Any]]] = None
    query_tokens = set(query_norm.split())
    for row in rows:
        product = dict(row)
        score = 0
        product_name = _normalize(product.get("product_name"))
        sku = _normalize(product.get("sku"))
        code = _normalize(product.get("product_code"))

        for field in [product_name, sku, code]:
            if field and f" {field} " in query_norm:
                score = max(score, 1000 + len(field))

        tokens = set(product_name.split())
        overlap = len(tokens.intersection(query_tokens))
        if tokens and overlap >= min(3, len(tokens)):
            score = max(score, 100 + overlap * 10)

        if score > 0 and (best is None or score > best[0]):
            best = (score, product)
    return best[1] if best else None


async def _find_warehouse(query: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
    q = _normalize(query)
    rows = (
        await db.execute(text("SELECT warehouse_id, warehouse_name, city, warehouse_code FROM warehouses"))
    ).mappings().all()
    for row in rows:
        tokens = [
            _normalize(row.get("city")),
            _normalize(row.get("warehouse_name")),
            _normalize(row.get("warehouse_code")),
        ]
        if any(token and token in q for token in tokens):
            return dict(row)
    return None


async def _subject_hints(query: str, db: AsyncSession) -> Dict[str, Any]:
    product = await _find_product(query, db)
    catalog_subjects = await _resolve_catalog_subjects(query, db)
    categories = list(dict.fromkeys([
        *await _db_categories(query, db),
        *catalog_subjects["resolved_categories"],
    ]))
    if product and product.get("category"):
        categories = list(dict.fromkeys([*categories, str(product["category"])]))
        catalog_subjects["unsupported_terms"] = []
    warehouse = await _find_warehouse(query, db)
    return {
        "explicit_product": product,
        "explicit_warehouse": warehouse,
        "explicit_categories": categories,
        "unsupported_catalog_terms": catalog_subjects["unsupported_terms"],
        "available_categories": catalog_subjects["available_categories"],
        "instruction": (
            "If explicit_categories is non-empty and explicit_product is null, filter by category columns. "
            "Do not filter product_name using a category word."
        ),
    }


def _sql_tables(sql: str) -> Set[str]:
    return {
        match.group(2)
        for match in re.finditer(r"\b(from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", sql, re.I)
    }


def _validate_sql(sql: str, allowed_tables: Sequence[str]) -> Tuple[bool, str]:
    if not sql or not isinstance(sql, str):
        return False, "SQL is empty."
    statement = sql.strip().rstrip(";").strip()
    if not re.match(r"^select\b", statement, re.I):
        return False, "Only SELECT statements are allowed."
    if ";" in statement:
        return False, "Multiple SQL statements are not allowed."
    if "--" in statement or "/*" in statement or "*/" in statement:
        return False, "SQL comments are not allowed."
    blocked = r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b"
    if re.search(blocked, statement, re.I):
        return False, "Write or schema-changing SQL is blocked."

    used_tables = _sql_tables(statement)
    disallowed = used_tables.difference(set(allowed_tables))
    if disallowed:
        return False, f"Query referenced tables/views outside allowed scope: {sorted(disallowed)}"
    if not used_tables:
        return False, "Query must reference at least one allowed table or view."

    if not re.search(r"\blimit\s+\d+\b", statement, re.I):
        has_aggregate = bool(re.search(r"\b(count|sum|avg|min|max)\s*\(", statement, re.I))
        has_group_by = bool(re.search(r"\bgroup\s+by\b", statement, re.I))
        if not has_aggregate or has_group_by:
            statement += " LIMIT 50"
    return True, statement


def _subject_filter_ok(query: str, sql: str, hints: Dict[str, Any], selected_tables: Sequence[str]) -> Tuple[bool, str]:
    sql_norm = _normalize(sql)

    categories = [str(c) for c in hints.get("explicit_categories") or []]
    product = hints.get("explicit_product") or {}
    if categories and not product:
        for category in categories:
            category_norm = _normalize(category)
            singular = category_norm[:-1] if category_norm.endswith("s") else category_norm
            if "category" not in sql_norm or (category_norm not in sql_norm and singular not in sql_norm):
                return False, f"SQL missed requested category filter: {category}."

    if isinstance(product, dict) and product.get("product_id"):
        product_tokens = [
            f"product id {int(product['product_id'])}",
            _normalize(product.get("product_name")),
            _normalize(product.get("sku")),
            _normalize(product.get("product_code")),
        ]
        if not any(token and token in sql_norm for token in product_tokens):
            return False, "SQL missed the requested product filter."

    warehouse = hints.get("explicit_warehouse") or {}
    if isinstance(warehouse, dict) and warehouse.get("warehouse_id"):
        warehouse_tokens = [
            _normalize(warehouse.get("city")),
            _normalize(warehouse.get("warehouse_name")),
            _normalize(warehouse.get("warehouse_code")),
        ]
        if not any(token and token in sql_norm for token in warehouse_tokens):
            return False, "SQL missed the requested warehouse/location filter."

    return True, ""


async def _generate_sql(
    query: str,
    selected_tables: List[str],
    schema: Dict[str, List[Dict[str, Any]]],
    hints: Dict[str, Any],
) -> Optional[str]:
    user_message = f"""
User question:
{query}

Selected tables/views:
{json.dumps(selected_tables, indent=2)}

Actual SQLite schema:
{json.dumps(schema, indent=2, default=str)}

Recognized subject filters:
{json.dumps(hints, indent=2, default=str)}

Known relationships:
{json.dumps(TABLE_RELATIONSHIPS, indent=2)}

Relevant SQL examples:
{json.dumps(matching_few_shots(query, selected_tables), indent=2, default=str)}
"""
    raw = await _call_model(SQL_GENERATION_PROMPT, user_message, temperature=0.0)
    parsed = _json_object(raw) or {}
    sql = parsed.get("sql")
    if isinstance(sql, str):
        return sql
    logger.warning(f"SQL generation failed. Raw model output: {raw}")
    return None


async def _repair_sql(
    query: str,
    selected_tables: List[str],
    schema: Dict[str, List[Dict[str, Any]]],
    failed_sql: str,
    error: str,
) -> Optional[str]:
    user_message = f"""
User question:
{query}

Selected tables/views:
{json.dumps(selected_tables, indent=2)}

Actual SQLite schema:
{json.dumps(schema, indent=2, default=str)}

Known relationships:
{json.dumps(TABLE_RELATIONSHIPS, indent=2)}

Failed SQL:
{failed_sql}

Validation/database error:
{error}
"""
    raw = await _call_model(SQL_REPAIR_PROMPT, user_message, temperature=0.0)
    parsed = _json_object(raw) or {}
    sql = parsed.get("sql")
    return sql if isinstance(sql, str) else None


async def _execute_sql(db: AsyncSession, sql: str) -> List[Dict[str, Any]]:
    rows = (await db.execute(text(sql))).mappings().all()
    return [dict(row) for row in rows[:MAX_RESULT_ROWS]]


def _chart(rows: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    if not rows:
        return []
    if _wants_table_output(query):
        return []
    label_keys = ["label", "product_name", "supplier_name", "warehouse_city", "date", "day", "category"]
    value_keys = [
        "value",
        "revenue",
        "units_sold",
        "predicted_units",
        "current_stock",
        "available_stock",
        "orders",
        "total_returns",
        "composite_score",
        "ai_score",
    ]
    first = rows[0]
    label_key = next((key for key in label_keys if key in first), None)
    value_key = next((key for key in value_keys if isinstance(first.get(key), (int, float))), None)
    if not label_key or not value_key:
        return []
    return [
        {"label": str(row.get(label_key) or "N/A"), "value": float(row.get(value_key) or 0)}
        for row in rows[:8]
    ]


async def _expand_tables(
    query: str,
    db: AsyncSession,
    original_plan: Dict[str, Any],
    failure_reason: str,
    *,
    intent_plan: Optional[Dict[str, Any]] = None,
    parent_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LLM-owned table expansion after empty/failed result.

    No business-specific fallback like "if stock then inventory".
    The LLM gets the failure, selected tables, hints, and full table context.
    """
    overview = str((intent_plan or {}).get("data_overview") or await _data_overview(db))
    hints = await _subject_hints(query, db)

    generic_candidates = [
        table
        for table in _fallback_tables(query)
        if table not in set(original_plan.get("tables", []))
    ]

    user_message = f"""
Original user message:
{parent_query or query}

Standalone task/question:
{query}

Detected intent plan:
{json.dumps(intent_plan or {}, indent=2, default=str)}

Data overview:
{overview}

Recognized database hints:
{json.dumps(hints, indent=2, default=str)}

Original selected tables:
{json.dumps(original_plan.get("tables", []), indent=2)}

Tables suggested by first selector if empty:
{json.dumps(original_plan.get("needs_more_if_empty", []), indent=2)}

Generic schema-overlap candidates:
{json.dumps(generic_candidates, indent=2)}

Failure or empty-result reason:
{failure_reason}

Available database context:
{_truncate(_available_table_context(), max_chars=24000)}

Instructions:
- Reconsider the table/view selection using business meaning, relationships, and the failure reason.
- Select a better table set if another table/view is needed.
- Do not generate SQL.
- Return only valid JSON.
"""

    raw = await _call_model(TABLE_EXPANSION_PROMPT, user_message, temperature=0.0)
    parsed = _json_object(raw) or {}

    tables = parsed.get("tables", [])
    if not isinstance(tables, list):
        tables = []

    selected = [
        table
        for table in tables
        if isinstance(table, str) and table in TABLE_DESCRIPTIONS
    ]

    if not selected:
        fallback_sources = [
            *(original_plan.get("needs_more_if_empty") or []),
            *generic_candidates,
            *(original_plan.get("tables") or []),
        ]
        selected = [
            table
            for table in fallback_sources
            if isinstance(table, str) and table in TABLE_DESCRIPTIONS
        ]

    return {
        "tables": list(dict.fromkeys(selected))[:MAX_SELECTED_TABLES],
        "reason": parsed.get("reason") or "LLM expansion unavailable; generic related-table fallback used.",
        "needs_more_if_empty": [],
    }
    
    
async def _sql_attempt(
    query: str,
    db: AsyncSession,
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    selected_tables = list(dict.fromkeys(plan.get("tables", [])))[:MAX_SELECTED_TABLES]

    schema = await _table_schema(db, selected_tables)
    selected_tables = [table for table in selected_tables if table in schema]

    if not selected_tables:
        return _empty_data_context(
            plan,
            "No real SQLite schema was found for the selected tables/views.",
            selected_tables=[],
        )

    schema = {table: schema[table] for table in selected_tables}
    hints = await _subject_hints(query, db)

    sql = await _generate_sql(query, selected_tables, schema, hints)
    if not sql:
        return _empty_data_context(
            plan,
            "SQL generation failed or returned invalid JSON.",
            selected_tables=selected_tables,
        )

    ok, safe_sql_or_error = _validate_sql(sql, selected_tables)

    if not ok:
        repaired_sql = await _repair_sql(
            query=query,
            selected_tables=selected_tables,
            schema=schema,
            failed_sql=sql,
            error=safe_sql_or_error,
        )

        if repaired_sql:
            ok, safe_sql_or_error = _validate_sql(repaired_sql, selected_tables)
            if not ok:
                return _empty_data_context(
                    plan,
                    safe_sql_or_error,
                    selected_tables=selected_tables,
                    generated_sql=repaired_sql,
                )
        else:
            return _empty_data_context(
                plan,
                safe_sql_or_error,
                selected_tables=selected_tables,
                generated_sql=sql,
            )

    safe_sql = safe_sql_or_error

    try:
        rows = await _execute_sql(db, safe_sql)
    except Exception as exc:
        repaired_sql = await _repair_sql(
            query=query,
            selected_tables=selected_tables,
            schema=schema,
            failed_sql=safe_sql,
            error=str(exc),
        )

        if not repaired_sql:
            return _empty_data_context(
                plan,
                str(exc),
                selected_tables=selected_tables,
                sql=safe_sql,
            )

        ok, repaired_safe_sql_or_error = _validate_sql(repaired_sql, selected_tables)
        if not ok:
            return _empty_data_context(
                plan,
                repaired_safe_sql_or_error,
                selected_tables=selected_tables,
                generated_sql=repaired_sql,
            )

        safe_sql = repaired_safe_sql_or_error

        try:
            rows = await _execute_sql(db, safe_sql)
        except Exception as second_exc:
            return _empty_data_context(
                plan,
                str(second_exc),
                selected_tables=selected_tables,
                sql=safe_sql,
            )

    return {
        "tool": "llm_sql_agent",
        "selected_tables": selected_tables,
        "table_selection_reason": plan.get("reason", ""),
        "sql": safe_sql,
        "rows": rows,
        "row_count": len(rows),
        "chart": _chart(rows, query),
    }
    

def _empty_data_context(
    plan: Dict[str, Any],
    error: str,
    *,
    selected_tables: Optional[List[str]] = None,
    sql: Optional[str] = None,
    generated_sql: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "tool": "llm_sql_agent",
        "selected_tables": selected_tables or plan.get("tables", []),
        "table_selection_reason": plan.get("reason", ""),
        "sql": sql,
        "generated_sql": generated_sql,
        "error": error,
        "rows": [],
        "row_count": 0,
    }


async def _answer_single_data_query(
    query: str,
    db: AsyncSession,
    *,
    intent_plan: Optional[Dict[str, Any]] = None,
    parent_query: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full single-task data workflow:
    LLM selects tables -> code fetches schema -> LLM generates SQL -> code executes ->
    if failed/empty, LLM expands tables and tries once more.
    """
    plan = await _select_tables(
        query,
        db,
        intent_plan=intent_plan,
        parent_query=parent_query,
    )

    first = await _sql_attempt(query, db, plan)

    if first.get("row_count", 0) > 0:
        first["attempts"] = [
            {
                "stage": "first_attempt",
                "selected_tables": first.get("selected_tables", []),
                "sql": first.get("sql"),
                "row_count": first.get("row_count", 0),
                "error": first.get("error"),
            }
        ]
        return first

    expanded_plan = await _expand_tables(
        query,
        db,
        plan,
        first.get("error") or "First SQL attempt returned zero rows.",
        intent_plan=intent_plan,
        parent_query=parent_query,
    )

    if expanded_plan.get("tables") == plan.get("tables"):
        first["attempts"] = [
            {
                "stage": "first_attempt",
                "selected_tables": first.get("selected_tables", []),
                "sql": first.get("sql"),
                "generated_sql": first.get("generated_sql"),
                "row_count": first.get("row_count", 0),
                "error": first.get("error"),
            }
        ]
        return first

    second = await _sql_attempt(query, db, expanded_plan)

    second["attempts"] = [
        {
            "stage": "first_attempt",
            "selected_tables": first.get("selected_tables", []),
            "sql": first.get("sql"),
            "generated_sql": first.get("generated_sql"),
            "row_count": first.get("row_count", 0),
            "error": first.get("error"),
        },
        {
            "stage": "expanded_attempt",
            "selected_tables": second.get("selected_tables", []),
            "sql": second.get("sql"),
            "generated_sql": second.get("generated_sql"),
            "row_count": second.get("row_count", 0),
            "error": second.get("error"),
        },
    ]

    return second


async def _answer_data_query(
    query: str,
    db: AsyncSession,
    intent_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Handles single and multi-part user questions.

    Planner decides task split.
    Each data task goes through the same LLM table -> SQL -> execute flow.
    Partial failures are preserved so narration can answer successful parts.
    """
    plan = await _plan_query(query, db, intent_plan)
    tasks = [task for task in plan.get("tasks", []) if isinstance(task, dict)]

    if not tasks:
        tasks = [{
            "id": "task_1",
            "type": "data_query",
            "question": query,
            "recognized_terms": [],
            "unsupported_terms": [],
            "reason": "Fallback single task because planner returned no usable tasks.",
        }]

    if (
        len(tasks) == 1
        and tasks[0].get("type") == "data_query"
        and str(tasks[0].get("question") or "").strip() == query.strip()
    ):
        context = await _answer_single_data_query(
            query,
            db,
            intent_plan=intent_plan,
            parent_query=query,
        )
        context["query_plan"] = plan
        return context

    parts: List[Dict[str, Any]] = []
    total_rows = 0

    for task in tasks[:6]:
        task_type = str(task.get("type") or "data_query").strip().lower()
        question = str(task.get("question") or query).strip() or query

        if task_type == "data_query":
            context = await _answer_single_data_query(
                question,
                db,
                intent_plan=intent_plan,
                parent_query=query,
            )

        elif task_type == "conversation":
            context = {
                "tool": "conversation",
                "message": await _conversation_answer(question),
                "rows": [],
                "row_count": 0,
            }

        else:
            unsupported_terms = [
                str(term)
                for term in task.get("unsupported_terms") or []
            ]
            context = {
                "tool": "task_validation",
                "error": task.get("reason") or "This part is outside the available app/database scope.",
                "unsupported_terms": unsupported_terms,
                "rows": [],
                "row_count": 0,
            }

        total_rows += int(context.get("row_count") or 0)

        parts.append({
            "task": task,
            "data_context": context,
        })

    return {
        "tool": "multi_task_sql_agent",
        "query_plan": plan,
        "selected_tables": list(dict.fromkeys(
            table
            for part in parts
            for table in (part.get("data_context") or {}).get("selected_tables", [])
        )),
        "sql": None,
        "parts": parts,
        "rows": [],
        "row_count": total_rows,
    }
    

def _no_data_narrative(data_context: Dict[str, Any]) -> str:
    if data_context.get("tool") == "task_validation":
        unsupported = data_context.get("unsupported_terms") or []
        reason = data_context.get("error") or "This part is outside the available app/database scope."
        if unsupported:
            return f"**Could not answer this part**\n- Unsupported term(s): {', '.join(map(str, unsupported))}.\n- {reason}"
        return f"**Could not answer this part**\n- {reason}"

    if data_context.get("error"):
        return (
            "I could not fetch database results for this query because the database query failed. "
            f"Reason: {data_context['error']}"
        )
    return "I could not find matching records in the database for this query."


async def _narrate(query: str, data_context: Dict[str, Any]) -> str:
    """
    LLM-owned final business response.

    The code does not decide "table answer" or "no data answer" before the LLM.
    It passes evidence and lets the narration prompt explain rows, partial results,
    SQL failures, empty results, or unsupported parts.
    """
    if data_context.get("tool") == "multi_task_sql_agent":
        evidence = _compact_multi_task_context(data_context)
        response = await _call_model(
            NARRATION_PROMPT,
            (
                f"Original user query:\n{query}\n\n"
                f"Planned task evidence:\n{json.dumps(evidence, indent=2, default=str)}\n\n"
                "Write a structured Markdown answer. Answer successful parts, clearly mark failed/empty/unsupported parts, "
                "and give one combined takeaway. Use only the evidence."
            ),
            temperature=0.2,
        )
        return response or _multi_task_fallback_narrative(data_context, query)

    evidence = dict(data_context)

    if isinstance(evidence.get("rows"), list) and len(evidence["rows"]) > 40:
        evidence["rows"] = evidence["rows"][:40]
        evidence["note"] = "Rows were truncated to first 40 records for narration."

    response = await _call_model(
        NARRATION_PROMPT,
        (
            f"User query:\n{query}\n\n"
            f"Database evidence:\n{json.dumps(evidence, indent=2, default=str)}\n\n"
            "Write the final answer in clean Markdown. "
            "If rows exist, summarize and show a table when useful. "
            "If rows are empty or SQL failed, explain what happened using selected tables, SQL/error, and available evidence. "
            "Do not claim the database lacks a concept unless the evidence proves it."
        ),
        temperature=0.2,
    )

    if response:
        return response

    return _markdown_fallback_narrative(data_context, query)


async def _stream_narrative(
    query: str,
    data_context: Dict[str, Any],
) -> AsyncGenerator[str, None]:
    """
    Streaming version of LLM-owned narration.
    No hardcoded branch for table output or empty rows.
    """
    if data_context.get("tool") == "multi_task_sql_agent":
        evidence = _compact_multi_task_context(data_context)
        user_message = f"""
Original user query:
{query}

Planned task evidence:
{_truncate(evidence, max_chars=18000)}

Write a structured Markdown answer.
Answer successful parts, clearly mark failed/empty/unsupported parts, and give one combined takeaway.
Use only the evidence.
"""
    else:
        evidence = dict(data_context)
        if isinstance(evidence.get("rows"), list) and len(evidence["rows"]) > 40:
            evidence["rows"] = evidence["rows"][:40]
            evidence["note"] = "Rows were truncated to first 40 records for narration."

        user_message = f"""
User query:
{query}

Database evidence:
{_truncate(evidence, max_chars=18000)}

Write the final answer in clean Markdown.
If rows exist, summarize and show a table when useful.
If rows are empty or SQL failed, explain what happened using selected tables, SQL/error, and available evidence.
Do not claim the database lacks a concept unless the evidence proves it.
"""

    emitted = False

    async for token in _stream_model(NARRATION_PROMPT, user_message, temperature=0.2):
        emitted = True
        yield token

    if not emitted:
        fallback = (
            _multi_task_fallback_narrative(data_context, query)
            if data_context.get("tool") == "multi_task_sql_agent"
            else _markdown_fallback_narrative(data_context, query)
        )
        for i in range(0, len(fallback), 80):
            yield fallback[i:i + 80]
            

def _compact_multi_task_context(data_context: Dict[str, Any]) -> Dict[str, Any]:
    compact_parts = []
    for part in data_context.get("parts") or []:
        if not isinstance(part, dict):
            continue
        task = part.get("task") if isinstance(part.get("task"), dict) else {}
        context = part.get("data_context") if isinstance(part.get("data_context"), dict) else {}
        rows = context.get("rows")
        compact_context = dict(context)
        if isinstance(rows, list) and len(rows) > 20:
            compact_context["rows"] = rows[:20]
            compact_context["note"] = "Rows truncated to first 20 records for narration."
        compact_parts.append({"task": task, "data_context": compact_context})
    return {
        "query_plan": data_context.get("query_plan"),
        "row_count": data_context.get("row_count"),
        "parts": compact_parts,
    }


def _multi_task_fallback_narrative(data_context: Dict[str, Any], query: str = "") -> str:
    parts = [part for part in data_context.get("parts") or [] if isinstance(part, dict)]
    if not parts:
        return _no_data_narrative(data_context)

    lines = ["**Summary**"]
    answered = sum(1 for part in parts if int((part.get("data_context") or {}).get("row_count") or 0) > 0)
    lines.append(f"- Split the request into **{len(parts)} task(s)** and answered **{answered}** with live data.")

    for index, part in enumerate(parts, start=1):
        task = part.get("task") if isinstance(part.get("task"), dict) else {}
        context = part.get("data_context") if isinstance(part.get("data_context"), dict) else {}
        question = str(task.get("question") or f"Task {index}")
        lines.extend(["", f"**Task {index}: {question}**"])
        if int(context.get("row_count") or 0) > 0:
            task_answer = _markdown_fallback_narrative(context, question)
            lines.append(task_answer)
        else:
            lines.append(_no_data_narrative(context))

    lines.extend(["", "**Combined takeaway**"])
    if answered:
        lines.append("- Use the answered sections for decisions now; rerun the unsupported section after replacing unavailable catalog terms.")
    else:
        lines.append("- No live-data section returned usable rows, so the request needs a clearer supported product/category, location, or metric.")
    return "\n".join(lines)


def _markdown_fallback_narrative(data_context: Dict[str, Any], query: str = "") -> str:
    rows = data_context.get("rows")
    row_count = int(data_context.get("row_count") or 0)
    if not isinstance(rows, list) or not rows:
        return _no_data_narrative(data_context)

    if _wants_table_output(query):
        lines = [
            "**Summary**",
            f"- Found **{row_count} matching row(s)** from live data.",
            "",
            "**Results**",
            _format_markdown_table(rows, max_rows=min(_limit_from_query(query, 10), 25)),
        ]
        shown = min(_limit_from_query(query, 10), 25, len(rows))
        if row_count > shown:
            lines.append(f"- {row_count - shown} more matching row(s) were returned.")
        lines.extend(["", "**What it means**", *_fallback_takeaways(rows, query)])
        return "\n".join(lines)

    lines = [
        "**Summary**",
        f"- The database returned **{row_count} row(s)** for this question.",
        "",
        "**Key numbers**",
    ]
    first_rows = rows[:10]
    for row in first_rows:
        if not isinstance(row, dict):
            continue
        parts = []
        for key, value in list(row.items())[:6]:
            label = str(key).replace("_", " ").title()
            parts.append(f"{label}: {value}")
        if parts:
            lines.append(f"- {'; '.join(parts)}")
    if row_count > len(first_rows):
        lines.append(f"- Showing top {len(first_rows)} rows here; {row_count - len(first_rows)} more row(s) were returned.")
    lines.extend(["", "**What it means**", *_fallback_takeaways(rows, query)])
    return "\n".join(lines)


def _fallback_takeaways(rows: List[Dict[str, Any]], query: str = "") -> List[str]:
    visible_rows = [row for row in rows if isinstance(row, dict)]
    if not visible_rows:
        return ["- No usable rows were returned for interpretation."]

    first = visible_rows[0]
    columns = list(first.keys())
    numeric_columns = [
        key for key, value in first.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    label_columns = [key for key in columns if key not in numeric_columns]

    bullets = [f"- The query returned {len(visible_rows)} row(s); the first row reflects the SQL ordering."]
    if label_columns:
        label = label_columns[0]
        bullets.append(f"- First row `{label.replace('_', ' ').title()}`: {first.get(label)}.")
    if numeric_columns:
        metrics = ", ".join(f"{key.replace('_', ' ').title()}: {first.get(key)}" for key in numeric_columns[:3])
        bullets.append(f"- Key numeric values in the first row: {metrics}.")
    bullets.append("- The interpretation is limited to the returned database evidence.")
    return bullets


def _format_markdown_table(rows: List[Dict[str, Any]], *, max_rows: int = 10) -> str:
    visible_rows = [row for row in rows[:max_rows] if isinstance(row, dict)]
    if not visible_rows:
        return ""

    first_keys: List[str] = []
    for row in visible_rows:
        for key in row.keys():
            if key not in first_keys:
                first_keys.append(key)
    columns = first_keys[:10]

    def label(key: str) -> str:
        return key.replace("_", " ").title()

    def cell(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value).replace("|", "\\|")

    header = "| # | " + " | ".join(label(key) for key in columns) + " |"
    align = "|---:|" + "|".join("---" for _ in columns) + "|"
    body = [
        f"| {index} | " + " | ".join(cell(row.get(key)) for key in columns) + " |"
        for index, row in enumerate(visible_rows, start=1)
    ]
    return "\n".join([header, align, *body])


async def _call_llm(query: str, data_context: Dict[str, Any]) -> str:
    """Compatibility wrapper used by page-level Copilot insight builders."""
    response = await _call_model(
        NARRATION_PROMPT,
        (
            f"Instruction: {query}\n\n"
            f"Evidence:\n{json.dumps(data_context, indent=2, default=str)}\n\n"
            "Return only concise, evidence-based business wording."
        ),
        temperature=0.2,
    )
    return response or ""


def _followups(intent: str) -> List[str]:
    if intent == "data_query":
        return [
            "Show sales for this category",
            "Show stock by warehouse",
            "Compare suppliers",
            "Show demand forecast",
        ]
    return [
        "How are sales going this month?",
        "Show low stock products",
        "Forecast headphone demand next month",
    ]


async def run_copilot(
    query: str,
    db: AsyncSession,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    logger.info(f"Copilot query received: {query[:120]}")

    query_for_conversation = _query_with_context(query, context)

    intent_plan = await _detect_intent(query, db)
    intent = str(intent_plan.get("intent") or "unsupported")

    if intent == "conversation":
        narrative = await _conversation_answer(query_for_conversation)
        data_context = {
            "tool": "conversation",
            "intent_reason": intent_plan.get("reason"),
            "message": narrative,
            "rows": [],
            "row_count": 0,
        }

    elif intent == "unsupported":
        narrative = (
            "I can help with app guidance or live supply-chain data from this workspace, "
            "but this request is outside that scope."
        )
        data_context = {
            "tool": "unsupported",
            "intent_reason": intent_plan.get("reason"),
            "message": narrative,
            "rows": [],
            "row_count": 0,
        }

    else:
        data_context = await _answer_data_query(query, db, intent_plan)
        data_context["intent_reason"] = intent_plan.get("reason")

        # Always let LLM narrate database evidence, even if rows are empty.
        narrative = await _narrate(query, data_context)

    row_count = int(data_context.get("row_count") or 0)

    return {
        "query": query,
        "intent": intent,
        "tools_invoked": [
            {
                "tool_name": data_context.get("tool", intent),
                "parameters": {
                    "selected_tables": data_context.get("selected_tables", []),
                    "sql": data_context.get("sql"),
                    "intent_reason": intent_plan.get("reason"),
                },
                "result_summary": (
                    f"{row_count} rows returned"
                    if data_context.get("tool") in {"llm_sql_agent", "multi_task_sql_agent"}
                    else "conversation response"
                ),
            }
        ],
        "data_context": data_context,
        "narrative": narrative,
        "confidence": 0.85 if row_count else 0.55,
        "follow_up_suggestions": _followups(intent),
    }
     
    
def _query_with_context(query: str, context: Optional[Dict[str, Any]]) -> str:
    history = (context or {}).get("history")
    if not isinstance(history, list) or not history:
        return query
    compact_history = []
    for item in history[-4:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))[:12]
        content = str(item.get("content", ""))[:800]
        if role and content:
            compact_history.append({"role": role, "content": content})
    if not compact_history:
        return query
    return (
        "Use the short session history only to resolve pronouns, follow-up references, and omitted subjects. "
        "Answer the current user question, do not repeat the history.\n\n"
        f"Session history:\n{json.dumps(compact_history, ensure_ascii=False)}\n\n"
        f"Current question: {query}"
    )


async def stream_copilot(
    query: str,
    db: AsyncSession,
    context: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    query_for_conversation = _query_with_context(query, context)

    intent_plan = await _detect_intent(query, db)
    intent = str(intent_plan.get("intent") or "unsupported")

    yield f"data: {json.dumps({'type': 'intent', 'content': intent, 'reason': intent_plan.get('reason')})}\n\n"

    if intent == "conversation":
        data_context = {
            "tool": "conversation",
            "intent_reason": intent_plan.get("reason"),
            "message": await _conversation_answer(query_for_conversation),
            "rows": [],
            "row_count": 0,
        }

        yield f"data: {json.dumps({'type': 'data', 'content': json.dumps(data_context, default=str)})}\n\n"

        narrative = str(data_context["message"])
        for i in range(0, len(narrative), 32):
            yield f"data: {json.dumps({'type': 'narrative', 'content': narrative[i:i + 32]})}\n\n"

    elif intent == "unsupported":
        data_context = {
            "tool": "unsupported",
            "intent_reason": intent_plan.get("reason"),
            "message": (
                "I can help with app guidance or live supply-chain data from this workspace, "
                "but this request is outside that scope."
            ),
            "rows": [],
            "row_count": 0,
        }

        yield f"data: {json.dumps({'type': 'data', 'content': json.dumps(data_context, default=str)})}\n\n"

        narrative = str(data_context["message"])
        for i in range(0, len(narrative), 32):
            yield f"data: {json.dumps({'type': 'narrative', 'content': narrative[i:i + 32]})}\n\n"

    else:
        yield f"data: {json.dumps({'type': 'tool_call', 'content': 'Planning tasks, selecting tables, fetching schema, generating SQL, and running database query'})}\n\n"

        data_context = await _answer_data_query(query, db, intent_plan)
        data_context["intent_reason"] = intent_plan.get("reason")

        yield f"data: {json.dumps({'type': 'data', 'content': json.dumps(data_context, default=str)})}\n\n"

        # Always stream LLM narration for database results, even empty/error/table results.
        async for token in _stream_narrative(query, data_context):
            yield f"data: {json.dumps({'type': 'narrative', 'content': token})}\n\n"

    confidence = 0.85 if int(data_context.get("row_count") or 0) else 0.55

    yield f"data: {json.dumps({'type': 'done', 'content': '', 'confidence': confidence})}\n\n"