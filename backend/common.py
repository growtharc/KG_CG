from typing import Dict


def extract_info(summary: str) -> Dict:
    """Extract simple action/object/problem tags from ticket summary."""
    summary_lower = summary.lower()

    action = None
    if "delete" in summary_lower or "remove" in summary_lower:
        action = "DELETE"
    elif "access" in summary_lower or "permission" in summary_lower:
        action = "ACCESS"
    elif "create" in summary_lower:
        action = "CREATE"
    elif "update" in summary_lower or "move" in summary_lower:
        action = "UPDATE"

    obj = None
    if "opportunity" in summary_lower or "opp" in summary_lower:
        obj = "Opportunity"
    elif "account" in summary_lower:
        obj = "Account"
    elif "onboarding" in summary_lower:
        obj = "Onboarding"

    problem = None
    if "duplicate" in summary_lower:
        problem = "Duplicate"
    elif "access" in summary_lower:
        problem = "Access Issue"

    return {"action": action, "object": obj, "problem": problem}


def get_routing(info: Dict) -> str:
    """Suggest routing based on extracted info."""
    if info["action"] == "DELETE" and info["problem"] == "Duplicate":
        return "Data Quality Team"
    if info["action"] == "ACCESS":
        return "Salesforce Admin Team"
    if info["action"] == "DELETE":
        return "Data Operations Team"
    if info["action"] == "CREATE":
        return "Data Operations Team"
    return "General Support Queue"
