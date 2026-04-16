"""Base Vault Guard — AI-powered safety scoring for DeFi vaults on Base."""

from vault_guard.models import RiskProfile, SafetyGrade, VaultInfo
from vault_guard.scorer import score_vault
from vault_guard.yield_finder import find_safe_yields

__all__ = ["VaultInfo", "RiskProfile", "SafetyGrade", "score_vault", "find_safe_yields"]
