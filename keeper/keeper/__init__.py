"""keeper — "can I keep this fish?" Offline, verified CA fishing regulations.

The most defensible non-legal idea of the four: structured, offline, provenance-tracked
regulatory data over a 1.075M-angler CA resident base. The moat is exactly what a
chatbot can't do — current rules, micro-zone specific, with no signal at the lake.
"""
from .regdb import RegDB, Species, Rule
from .decide import can_i_keep, Decision, Verdict

__version__ = "0.1.0"
__all__ = ["RegDB", "Species", "Rule", "can_i_keep", "Decision", "Verdict"]
