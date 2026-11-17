"""DB-aware business operations (validation via ``app.rules``, writes, audit, notifications).

Routers stay thin and call these functions; Orion proposal acceptance reuses the same functions with
the accepting human as actor (BR-050). See PLAN.md §4.
"""
