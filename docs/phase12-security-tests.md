# Phase 12 security tests

Run migrations on an isolated PostgreSQL database, then run the backend suite.
The suite must include two users and two organizations, membership removal,
last-owner protection, invitation replay, resource IDOR, and RLS tests using a
non-owner runtime role. The local validation in this change passed the existing
37-test PostgreSQL suite; non-owner RLS verification is pending deployment
role provisioning.

