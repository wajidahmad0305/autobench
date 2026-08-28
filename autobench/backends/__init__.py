"""Per-category mock backends.

Each module exposes ``initialize(db_conn, task_spec)`` to seed an in-memory
SQLite database from the task's ``context.initial_state`` and
``dispatch(db_conn, tool_name, arguments)`` to run one tool against it.
``dispatch`` raises ``ValueError`` for a tool name unknown to that category.
"""

from autobench.backends import (
    crm_order_fulfilment,
    financial_reconciliation,
    hr_employee_lifecycle,
    it_access_provisioning,
)

__all__ = [
    "crm_order_fulfilment",
    "financial_reconciliation",
    "hr_employee_lifecycle",
    "it_access_provisioning",
]
