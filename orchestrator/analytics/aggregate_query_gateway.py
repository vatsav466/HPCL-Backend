"""
Generic SQL aggregation / filtered-read gateway for any single-table query.

Table name, column names, group keys, filters, date bounds, and aggregates all come from
caller input. Identifiers (table, columns, aliases) must match a strict pattern to limit
SQL injection risk; values are passed as bound-style literals only.

Execution uses :meth:`urdhva_base.postgresmodel.BasePostgresModel.get_aggr_data`.
"""
from __future__ import annotations

import datetime
import ast
import json
import re
import typing

import urdhva_base.postgresmodel as urdhva_pg

_SAFE_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_AGG_FUNCS = frozenset({"sum", "avg", "min", "max", "count"})


def _ident(name: str, *, kind: str = "identifier") -> str:
    if not name or not _SAFE_IDENT.match(name):
        raise ValueError(
            f"Invalid {kind} {name!r}; use ASCII letters, digits, underscore; "
            "must start with letter or underscore."
        )
    return name


def _qualified_table(name: str) -> str:
    """``table`` or ``schema.table`` with each segment validated."""
    parts = name.split(".")
    if len(parts) > 2:
        raise ValueError("Table must be `name` or `schema.name`.")
    return ".".join(_ident(p, kind="table segment") for p in parts)


def _sql_literal(val: typing.Any) -> str:
    if val is None:
        raise ValueError("Filter values must not be None; omit the key instead.")
    if isinstance(val, (datetime.date, datetime.datetime)):
        return f"'{val.isoformat()}'"
    if isinstance(val, str):
        return "'" + val.replace("'", "''") + "'"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    raise TypeError(f"Unsupported filter value type: {type(val)}")


def _agg_expression(fn: str, column: str) -> str:
    fn_l = fn.lower()
    if fn_l not in _AGG_FUNCS:
        raise ValueError(f"Unsupported aggregate {fn!r}; use {_AGG_FUNCS}.")
    if fn_l == "count" and column.strip() == "*":
        return "COUNT(*)"
    _ident(column, kind="aggregate column")
    if fn_l == "count":
        return f"COUNT({column})"
    return f"{fn_l.upper()}({column})"


def _build_where(
    filters: typing.Optional[typing.Mapping[str, typing.Any]],
    date_column: typing.Optional[str],
    date_from: typing.Optional[datetime.date],
    date_to: typing.Optional[datetime.date],
) -> typing.List[str]:
    parts: typing.List[str] = []
    if filters:
        for key, val in filters.items():
            c = _ident(key, kind="filter column")
            if isinstance(val, (list, tuple, set)):
                if not val:
                    parts.append("FALSE")
                    continue
                inner = ", ".join(_sql_literal(x) for x in val)
                parts.append(f"{c} IN ({inner})")
            else:
                parts.append(f"{c} = {_sql_literal(val)}")
    if date_from is not None or date_to is not None:
        if not date_column:
            raise ValueError("date_column is required when date_from or date_to is set.")
        dc = _ident(date_column, kind="date column")
        if date_from is not None:
            parts.append(f"{dc} >= {_sql_literal(date_from)}")
        if date_to is not None:
            parts.append(f"{dc} <= {_sql_literal(date_to)}")
    return parts


def _order_clause(
    order_by: typing.Optional[typing.Sequence[typing.Tuple[str, str]]],
    known_aliases: typing.Set[str],
) -> str:
    if not order_by:
        return ""
    bits: typing.List[str] = []
    for col, direction in order_by:
        d = direction.strip().upper()
        if d not in ("ASC", "DESC"):
            raise ValueError(f"ORDER BY direction must be ASC or DESC, got {direction!r}")
        if col in known_aliases:
            bits.append(f"{_ident(col, kind='alias')} {d}")
        else:
            bits.append(f"{_ident(col, kind='ORDER BY column')} {d}")
    return " ORDER BY " + ", ".join(bits)


async def query_aggregate_gateway(
    *,
    table: str,
    group_by: typing.Optional[typing.Sequence[str]] = None,
    filters: typing.Optional[typing.Mapping[str, typing.Any]] = None,
    date_column: typing.Optional[str] = None,
    date_from: typing.Optional[datetime.date] = None,
    date_to: typing.Optional[datetime.date] = None,
    aggregations: typing.Optional[list] = None,
    detail_fields: typing.Optional[list] = None,
    order_by: typing.Optional[list] = None,
    limit: int = 1000,
    skip: int = 0,
) -> typing.Mapping[str, typing.Any]:
    """
    Run a single-table ``SELECT`` with optional filters, date range, grouping, and
    aggregates. All structure is driven by arguments.

    **Parameters**

    * ``table`` — Physical table name, or ``schema.table`` (each segment validated).
    * ``group_by`` — Dimension columns for ``GROUP BY`` (validated identifiers).
    * ``filters`` — Equality or ``IN`` list: ``{"col": "x"}`` or ``{"col": ["a","b"]}``.
    * ``date_column`` — Column used with ``date_from`` / ``date_to`` (inclusive).
      Required if either date bound is set.
    * ``date_from`` / ``date_to`` — Inclusive bounds; optional.
    * ``aggregations`` — ``(output_alias, aggregate_fn, column)``; ``aggregate_fn`` is
      ``sum|avg|min|max|count``; use ``("n", "count", "*")`` for ``COUNT(*)``.
    * ``detail_fields`` — When not using aggregates, optional column list; default ``*``.
    * ``order_by`` — ``[(column_or_alias, "asc"|"desc"), ...]``.
    * ``limit`` / ``skip`` — Passed to ``get_aggr_data`` (offset = ``limit * skip``).

    **Modes**

    1. Detail: no ``group_by`` and no ``aggregations`` — filtered row scan.
    2. Global aggregates: ``aggregations`` without ``group_by`` — no ``GROUP BY``.
    3. Grouped: both ``group_by`` and ``aggregations`` — ``GROUP BY`` the dimensions.

    **Returns**

    ``{"data", "count", "total"}`` as from ``get_aggr_data``.
    """
    tsql = _qualified_table(table)
    where_parts = _build_where(filters, date_column, date_from, date_to)
    where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    gb_list: typing.List[str] = []
    if group_by:
        gb_list = [_ident(c, kind="GROUP BY column") for c in group_by]
        if not gb_list:
            raise ValueError("group_by must list at least one column when provided.")

    has_group = bool(gb_list)
    has_agg = bool(aggregations)

    if has_group and not has_agg:
        raise ValueError(
            "When group_by is set, aggregations must also be set. "
            "For raw rows, omit group_by and use filters only."
        )

    alias_names: typing.Set[str] = set()

    if has_agg:
        if aggregations is None:
            raise ValueError("aggregations is required when using aggregates.")
        aggregations = [ast.literal_eval(item) for item in aggregations]
        select_parts: typing.List[str] = []
        for c in gb_list:
            select_parts.append(c)
        for alias, fn, col in aggregations:
            a = _ident(alias, kind="aggregate alias")
            if a in alias_names:
                raise ValueError(f"Duplicate aggregate alias {a!r}")
            alias_names.add(a)
            expr = _agg_expression(fn, col)
            select_parts.append(f"{expr} AS {a}")
        group_sql = f" GROUP BY {', '.join(gb_list)}" if has_group else ""
        sql = f"SELECT {', '.join(select_parts)} FROM {tsql}{where_sql}{group_sql}"
    else:
        if detail_fields:
            fields_sql = ", ".join(_ident(f, kind="detail field") for f in detail_fields)
        else:
            fields_sql = "*"
        sql = f"SELECT {fields_sql} FROM {tsql}{where_sql}"

    order_by = [ast.literal_eval(item) for item in order_by]
    sql += _order_clause(order_by, alias_names)

    return await urdhva_pg.BasePostgresModel.get_aggr_data(
        sql,
        limit=limit,
        skip=skip,
        skip_total=True,
    )
