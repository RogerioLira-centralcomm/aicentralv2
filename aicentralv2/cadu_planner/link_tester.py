"""Compatibility import for reports-owned link diagnostics.

New product code must import ``cadu_connect.reports_link_tester``. This alias
keeps existing agent tools and integrations working while they transition.
"""
import sys

from ..cadu_connect import reports_link_tester

sys.modules[__name__] = reports_link_tester
