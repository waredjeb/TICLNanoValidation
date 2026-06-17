"""Preset validation suites."""

# Define validation suites as lists of module names

VALIDATION_SUITES = {
    "quick": [
        "distributions",
    ],

    "matching_only": [
        "matching",
    ],

    "performance": [
        "distributions",
        "matching",
        "efficiency",
    ],

    "full_validation": [
        "distributions",
        "matching",
        "efficiency",
        "resolution",
    ],

    "resolution_study": [
        "matching",  # Required dependency
        "resolution",
    ],

    "efficiency_study": [
        "matching",  # Required dependency
        "efficiency",
    ],
}


def get_suite(suite_name: str) -> list:
    """
    Get list of modules for a validation suite.

    Args:
        suite_name: Name of the suite

    Returns:
        List of module names

    Raises:
        ValueError: If suite name is not recognized
    """
    if suite_name not in VALIDATION_SUITES:
        available = ", ".join(VALIDATION_SUITES.keys())
        raise ValueError(
            f"Unknown validation suite '{suite_name}'. "
            f"Available suites: {available}"
        )

    return VALIDATION_SUITES[suite_name]


def list_suites() -> dict:
    """
    Get all available validation suites.

    Returns:
        Dictionary mapping suite names to module lists
    """
    return VALIDATION_SUITES.copy()
