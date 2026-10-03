"""Creative Lab: internal bench for image models (Studio host, /lab), gated by organization.

Isolated from the Studio production pipeline: it reads brands and audits, reuses pure helpers and the
logo Composer, and writes only to cx_lab_* tables.
"""
