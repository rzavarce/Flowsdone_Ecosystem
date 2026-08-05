"""Domain layer: framework-agnostic models and port interfaces.

Contains the core business models (Pydantic) and the Protocol
definitions (ports) that adapters implement. Nothing in this package
may import from adapters or infrastructure.
"""
