"""Field Permissions and Classification Service.

Classifies intake record attributes as Identity vs. Clinical:
- field_worker: May only view and edit Identity fields.
- doctor / admin: May view, edit, review, and approve both Identity and Clinical fields.

Fail-closed: Any field not explicitly registered in IDENTITY_FIELDS is treated as clinical.
"""

from typing import Set, Dict, Any, List, Tuple

# Approved Single Shared Identity Fields Specification (Rule 4.1)
IDENTITY_FIELDS: Set[str] = {
    "person_name",
    "full_name",
    "name",
    "dob",
    "date_of_birth",
    "age",
    "gender",
    "sex",
    "mobile_number",
    "phone",
    "emergency_contact_phone",
    "parent_guardian_name",
    "parent_name",
    "guardian_name",
    "address",
    "admission_id",
    "institution_name",
    "school_name",
    "class_grade",
    "class",
    "section",
    "roll_number",
    "blood_group"
}

CLINICAL_FIELDS: Set[str] = {
    "height",
    "height_cm",
    "weight",
    "weight_kg",
    "bmi",
    "bmi_category",
    "blood_pressure",
    "bp",
    "pulse",
    "pulse_bpm",
    "rbs",
    "waist_circumference",
    "known_allergies",
    "allergies",
    "examination_details",
    "referral_details",
    "referral_reason",
    "referral_specialist",
    "vital_signs_status",
    "gait_status",
    "ears_hearing_status",
    "otoscopy_findings",
    "oral_cavity_throat",
    "oral_hygiene",
    "dental_caries",
    "malocclusion",
    "lymph_nodes",
    "vision_distant_right",
    "vision_distant_left",
    "color_vision",
    "squint_strabismus",
    "systemic_findings",
    "paediatric_alerts",
    "reviewer_notes",
    "notes"
}


def is_identity_field(field_name: str) -> bool:
    """Return True if field belongs to identity group."""
    if not field_name or not isinstance(field_name, str):
        return False
    return field_name.strip().lower() in IDENTITY_FIELDS


def is_clinical_field(field_name: str) -> bool:
    """Return True if field is clinical. Fails closed: any non-identity field is clinical."""
    return not is_identity_field(field_name)


def validate_field_worker_edits(payload: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate whether an update payload touches any clinical fields.
    Returns (is_valid: bool, disallowed_fields: List[str]).
    """
    disallowed = []
    for k in payload.keys():
        if k in ("id", "camp_id", "community_id", "created_at", "updated_at", "status", "scanned_by"):
            continue
        if is_clinical_field(k):
            disallowed.append(k)

    return (len(disallowed) == 0, disallowed)


def filter_editable_fields(payload: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Filter fields that can be edited by the given role."""
    norm_role = "field_worker" if role == "worker" else (role or "field_worker").lower()
    if norm_role in ("doctor", "admin", "superuser"):
        return payload

    # field_worker: keep only identity fields
    return {k: v for k, v in payload.items() if is_identity_field(k)}
