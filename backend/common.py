from typing import Dict


def extract_info(summary: str) -> Dict:
    """Extract action, object, issue_type, and resolution from a ticket summary."""
    s = summary.lower()

    # --- action (priority order) ---
    action = None
    if "delete" in s or "remove" in s:
        action = "DELETE"
    elif "merge" in s or "deduplic" in s:
        action = "MERGE"
    elif "access" in s or "permission" in s:
        action = "ACCESS"
    elif "reassign" in s or "transfer" in s:
        action = "REASSIGN"
    elif "create" in s or "add" in s:
        action = "CREATE"
    elif "update" in s or "edit" in s or "move" in s or "flip" in s or "change" in s or "roll" in s:
        action = "UPDATE"
    elif "churn" in s:
        action = "CHURN"

    # --- object ---
    obj = None
    if "opportunity" in s or " opp" in s or "opp " in s or s.startswith("opp"):
        obj = "Opportunity"
    elif "onboarding" in s or "ob record" in s:
        obj = "Onboarding"
    elif "account" in s:
        obj = "Account"
    elif "case" in s:
        obj = "Case"
    elif "lead" in s:
        obj = "Lead"
    elif "contact" in s:
        obj = "Contact"
    elif "report" in s:
        obj = "Report"

    # --- issue_type ---
    issue_type = None
    if "duplicate" in s or "duplicat" in s:
        issue_type = "Duplicate"
    elif "permission" in s or "access" in s:
        issue_type = "Permission"
    elif "data quality" in s or "corrupt" in s:
        issue_type = "DataQuality"
    elif "integration" in s or "sync" in s or "not syncing" in s:
        issue_type = "Integration"
    elif "missing" in s or "not found" in s:
        issue_type = "MissingData"
    elif "onboarding" in s or "ob record" in s or "churn" in s:
        issue_type = "OnboardingOps"
    elif "opportunity" in s or " opp" in s:
        issue_type = "OpportunityOps"
    elif "status" in s or "stage" in s or "flip" in s:
        issue_type = "StatusUpdate"

    # --- resolution (inferred from action + object) ---
    resolution = None
    if action == "MERGE":
        resolution = "MergeRecords"
    elif action == "ACCESS" or issue_type == "Permission":
        resolution = "GrantAccess"
    elif action == "DELETE" and obj == "Opportunity":
        resolution = "DeleteRecord"
    elif action == "DELETE" and obj == "Onboarding":
        resolution = "DeleteOBRecord"
    elif action == "DELETE":
        resolution = "DeleteRecord"
    elif action == "REASSIGN":
        resolution = "ReassignRecord"
    elif action == "CREATE" and obj == "Opportunity":
        resolution = "CreateOpportunity"
    elif action == "CREATE":
        resolution = "CreateRecord"
    elif action == "CHURN":
        resolution = "ChurnOBRecord"
    elif action == "UPDATE":
        resolution = "UpdateRecord"
    elif issue_type == "Integration":
        resolution = "TriggerSync"

    return {
        "action": action,
        "object": obj,
        "issue_type": issue_type,
        "resolution": resolution,
    }


def get_routing(info: Dict) -> str:
    """Suggest routing team based on extracted info."""
    if info.get("issue_type") == "Duplicate":
        return "Data Quality Team"
    if info.get("issue_type") == "Permission":
        return "Salesforce Admin Team"
    if info.get("issue_type") == "Integration":
        return "Integration Team"
    if info.get("action") in ("DELETE", "MERGE", "CHURN"):
        return "Data Operations Team"
    if info.get("action") == "CREATE":
        return "Data Operations Team"
    if info.get("action") == "UPDATE":
        return "Data Operations Team"
    return "General Support Queue"
