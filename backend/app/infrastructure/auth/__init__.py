"""Pluggable authentication infrastructure.

Provides adapters for external identity providers (Supabase, Firebase).
Each adapter is a pure decoder: it accepts a raw token and returns
normalised ``AuthClaims``.
"""
