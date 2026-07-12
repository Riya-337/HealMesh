"""
healmesh-core/tests/test_audit.py

Reflection-based tests for AuditLogger.

INVARIANT (Constitution Article 2, Invariant 5):
The AuditLogger class must have NO update() or delete() methods.
These tests verify that invariant at the class level via Python reflection.

If these tests fail, it means someone added a mutation method to AuditLogger,
which is a violation of the Constitution.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from audit.logger import AuditLogger


def test_logger_class_exists():
    """AuditLogger can be imported and instantiated with a DSN."""
    logger = AuditLogger(dsn="postgresql://fake:fake@localhost:5432/fake")
    assert logger is not None


def test_no_update_method_exists():
    """
    INVARIANT: AuditLogger must not have any 'update' method.
    If this test fails, a Constitution violation has been introduced.
    """
    members = dict(inspect.getmembers(AuditLogger, predicate=inspect.isfunction))
    update_methods = [name for name in members if "update" in name.lower()]
    assert update_methods == [], (
        f"CONSTITUTION VIOLATION: AuditLogger has update-like methods: {update_methods}. "
        "The audit log is append-only. Remove these methods immediately."
    )


def test_no_delete_method_exists():
    """
    INVARIANT: AuditLogger must not have any 'delete', 'remove', or 'purge' methods.
    If this test fails, a Constitution violation has been introduced.
    """
    members = dict(inspect.getmembers(AuditLogger, predicate=inspect.isfunction))
    forbidden = [
        name for name in members
        if any(word in name.lower() for word in ("delete", "remove", "purge", "truncate", "drop"))
    ]
    assert forbidden == [], (
        f"CONSTITUTION VIOLATION: AuditLogger has mutation methods: {forbidden}. "
        "The audit log is append-only. Remove these methods immediately."
    )


def test_public_methods_are_only_read_and_write():
    """
    All public methods on AuditLogger must be either log_ (write) or get_ (read).
    This enforces the append-only contract at the interface level.
    """
    members = dict(inspect.getmembers(AuditLogger, predicate=inspect.isfunction))
    public_methods = [
        name for name in members
        if not name.startswith("_")
    ]
    for method_name in public_methods:
        assert method_name.startswith("log_") or method_name.startswith("get_"), (
            f"CONSTITUTION VIOLATION: AuditLogger has unexpected public method '{method_name}'. "
            "Public methods must start with 'log_' (append) or 'get_' (read-only). "
            "Mutation methods are prohibited."
        )


def test_audit_logger_has_no_class_level_update_or_delete():
    """Check class __dict__ directly (catches staticmethods and classmethods too)."""
    class_dict_keys = list(AuditLogger.__dict__.keys())
    forbidden = [
        k for k in class_dict_keys
        if any(word in k.lower() for word in ("update", "delete", "remove", "purge", "truncate"))
    ]
    assert forbidden == [], (
        f"CONSTITUTION VIOLATION: AuditLogger class dict contains forbidden names: {forbidden}"
    )
