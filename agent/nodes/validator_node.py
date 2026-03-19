import sys
import pathlib
import re
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from config.schema import BillingState
from data.csv_loader import lookup_cpt, lookup_enm
from typing import List, Dict, Any
from loguru import logger

# ICD-10 format pattern: letter + digits, optionally with a dot
ICD10_PATTERN = re.compile(r'^[A-Z]\d{2}\.?\d{0,4}$')


# Valid E/M code ranges for office visits
VALID_EM_OFFICE_VISITS = {"99211", "99212", "99213", "99214", "99215"}
# Extended valid E/M codes (new patients, consultations, etc.)
VALID_EM_CODES_EXTENDED = {
    "99201", "99202", "99203", "99204", "99205",  # New patient office
    "99211", "99212", "99213", "99214", "99215",  # Established patient office
    "99221", "99222", "99223",  # Initial hospital care
    "99231", "99232", "99233",  # Subsequent hospital care
    "99241", "99242", "99243", "99244", "99245",  # Office consultations
}


def normalization_node(state: BillingState) -> BillingState:
    """
    Normalize LLM output so downstream nodes have consistent keys.
    Ensures lists/dicts are never None.
    Validates structure: each code object must have required fields.
    """
    raw = state.get("billing_response", {})
    
    # Normalize and validate CPT codes
    cpt_codes = raw.get("CPT_codes") or []
    valid_cpt_codes = []
    for code_obj in cpt_codes:
        if not isinstance(code_obj, dict):
            logger.warning(f"Skipping non-dict CPT code entry: {code_obj}")
            continue
        if not code_obj.get("code"):
            logger.warning(f"Removing CPT code object missing 'code' field: {code_obj}")
            continue
        valid_cpt_codes.append(code_obj)
    
    if len(valid_cpt_codes) != len(cpt_codes):
        logger.info(f"Normalization: removed {len(cpt_codes) - len(valid_cpt_codes)} malformed CPT codes")
    
    # Normalize and validate E/M codes
    em_codes = raw.get("E_M_codes") or []
    valid_em_codes = []
    for code_obj in em_codes:
        if not isinstance(code_obj, dict):
            logger.warning(f"Skipping non-dict E/M code entry: {code_obj}")
            continue
        if not code_obj.get("code"):
            logger.warning(f"Removing E/M code object missing 'code' field: {code_obj}")
            continue
        valid_em_codes.append(code_obj)
    
    if len(valid_em_codes) != len(em_codes):
        logger.info(f"Normalization: removed {len(em_codes) - len(valid_em_codes)} malformed E/M codes")
    
    # Normalize ICD10 codes
    icd_codes = raw.get("ICD10_codes") or []
    valid_icd_codes = []
    for code_obj in icd_codes:
        if not isinstance(code_obj, dict):
            logger.warning(f"Skipping non-dict ICD10 code entry: {code_obj}")
            continue
        if not code_obj.get("code"):
            logger.warning(f"Removing ICD10 code object missing 'code' field: {code_obj}")
            continue
        valid_icd_codes.append(code_obj)
    
    state["billing_response"] = {
        "CPT_codes": valid_cpt_codes,
        "E_M_codes": valid_em_codes,
        "ICD10_codes": valid_icd_codes,
        "procedure_details": raw.get("procedure_details") or {},
    }
    
    logger.info(f"Normalization complete: {len(valid_cpt_codes)} CPT, {len(valid_em_codes)} E/M, {len(valid_icd_codes)} ICD10 codes")

    return state


async def cpt_validator_node(state: BillingState) -> BillingState:
    """
    Validate CPT codes against CSV data.
    Handles LLM dict output, exceptions, and keeps async for graph compatibility.
    Includes business logic for quantity limits and detailed logging.
    """
    cpt_candidates: List[Dict[str, Any]] = state.get("billing_response", {}).get("CPT_codes", [])
    state["validated_cpt"] = []
    
    # Initialize validation errors tracking
    if "validation_errors" not in state:
        state["validation_errors"] = []  # type: ignore

    if not cpt_candidates:
        logger.info("No CPT code candidates to validate")
        return state

    accepted_codes = []
    rejected_codes = []

    for code_entry in cpt_candidates:
        try:
            code = code_entry.get("code")
            if not code:
                rejected_codes.append({"code": None, "reason": "missing code field"})
                continue

            row = lookup_cpt(code)
            
            if not row:
                rejected_codes.append({"code": code, "reason": "code not found in CSV data"})
                logger.warning(f"CPT code '{code}' not found in CSV data - rejected")
                continue

            # Extract CSV values by column name
            db_code_info = {
                "proCode": row.get("proCode", ""),
                "codeDesc": row.get("codeDesc", ""),
                "minQty": int(row.get("minQty", 0) or 0),
                "maxQty": int(row.get("maxQty", 0) or 0),
                "minSize": float(row.get("minSize", 0) or 0),
                "maxSize": float(row.get("maxSize", 0) or 0),
                "chargePerUnit": int(row.get("chargePerUnit", 0) or 0),
                "billWithIntEM": int(row.get("billWithIntEM", 0) or 0),
                "billWithFUEM": int(row.get("billWithFUEM", 0) or 0),
                "leftRightSepration": int(row.get("leftRightSepration", 0) or 0),
                "billAlone": int(row.get("billAlone", 0) or 0),
                "splitInMultipleVisits": int(row.get("splitInMultipleVisits", 0) or 0),
                "effectiveSince": row.get("effectiveSince", "")
            }

            # Check quantity limits if present
            requested_qty = code_entry.get("quantity", code_entry.get("Quantity", 1))
            min_qty = db_code_info.get("minQty")
            max_qty = db_code_info.get("maxQty")

            if min_qty is not None and requested_qty < min_qty:
                rejected_codes.append({
                    "code": code, 
                    "reason": f"quantity {requested_qty} below minimum {min_qty}"
                })
                logger.warning(f"CPT code '{code}' rejected: quantity {requested_qty} below minimum {min_qty}")
                continue

            if max_qty is not None and max_qty > 0 and requested_qty > max_qty:
                rejected_codes.append({
                    "code": code, 
                    "reason": f"quantity {requested_qty} exceeds maximum {max_qty}"
                })
                logger.warning(f"CPT code '{code}' rejected: quantity {requested_qty} exceeds maximum {max_qty}")
                continue

            # Code is valid - add to validated list
            db_code_info["requested_qty"] = requested_qty
            db_code_info["original_entry"] = code_entry
            state["validated_cpt"].append(db_code_info)
            accepted_codes.append(code)
            logger.info(f"CPT code '{code}' validated successfully: {db_code_info.get('codeDesc', 'N/A')}")

        except KeyError as e:
            logger.error(f"KeyError processing CPT code entry {code_entry}: {e}")
            rejected_codes.append({"code": code_entry.get("code"), "reason": f"KeyError: {e}"})
        except Exception as e:
            logger.error(f"Unexpected error processing CPT code entry {code_entry}: {e}")
            rejected_codes.append({"code": code_entry.get("code"), "reason": f"Error: {e}"})

    logger.info(f"CPT validation complete: {len(accepted_codes)} accepted, {len(rejected_codes)} rejected")
    if rejected_codes:
        logger.info(f"Rejected CPT codes: {rejected_codes}")

    return state


async def em_validator_node(state: BillingState) -> BillingState:
    """
    Validate E/M codes against CSV data.
    Handles dict input, exceptions, and keeps async for graph compatibility.
    Includes E/M level validation and modifier 25 checks.
    """
    em_candidates: List[Dict[str, Any]] = state.get("billing_response", {}).get("E_M_codes", [])
    state["validated_em"] = []
    
    # Initialize validation errors tracking
    if "validation_errors" not in state:
        state["validation_errors"] = []  # type: ignore

    if not em_candidates:
        logger.info("No E/M code candidates to validate")
        return state

    accepted_codes = []
    rejected_codes = []
    
    # Check if there are validated CPT procedure codes (for modifier 25 validation)
    validated_cpt_codes = state.get("validated_cpt", [])
    has_procedure_cpt = len(validated_cpt_codes) > 0

    for code_entry in em_candidates:
        try:
            code = code_entry.get("code")
            if not code:
                rejected_codes.append({"code": None, "reason": "missing code field"})
                continue

            # Validate E/M code is in valid range
            if code not in VALID_EM_CODES_EXTENDED:
                logger.warning(f"E/M code '{code}' not in valid E/M code range")
                # Still check CSV, but log the warning

            row = lookup_enm(code)
            
            if not row:
                rejected_codes.append({"code": code, "reason": "code not found in CSV data"})
                logger.warning(f"E/M code '{code}' not found in CSV data - rejected")
                continue

            db_code_info = {
                "enmCode": row.get("enmCode", ""),
                "enmCodeDesc": row.get("enmCodeDesc", ""),
                "enmType": row.get("enmType", ""),
                "facilityCode": row.get("facilityCode", ""),
                "enmLevel": int(row.get("enmLevel", 0) or 0),
                "original_entry": code_entry
            }

            # Check modifier 25 validation
            modifiers = code_entry.get("modifiers", [])
            has_modifier_25 = "25" in modifiers or 25 in modifiers
            
            if has_modifier_25 and not has_procedure_cpt:
                logger.warning(
                    f"E/M code '{code}' has modifier 25 but no procedure CPT codes in billing - "
                    "modifier 25 typically requires accompanying procedures"
                )
                # This is a warning, not a rejection - still accept the code

            # Code is valid - add to validated list
            state["validated_em"].append(db_code_info)
            accepted_codes.append(code)
            logger.info(f"E/M code '{code}' validated successfully: {db_code_info.get('enmCodeDesc', 'N/A')}")

        except KeyError as e:
            logger.error(f"KeyError processing E/M code entry {code_entry}: {e}")
            rejected_codes.append({"code": code_entry.get("code"), "reason": f"KeyError: {e}"})
        except Exception as e:
            logger.error(f"Unexpected error processing E/M code entry {code_entry}: {e}")
            rejected_codes.append({"code": code_entry.get("code"), "reason": f"Error: {e}"})

    logger.info(f"E/M validation complete: {len(accepted_codes)} accepted, {len(rejected_codes)} rejected")
    if rejected_codes:
        logger.info(f"Rejected E/M codes: {rejected_codes}")

    # Track rejection info for retry logic
    original_count = len(em_candidates)
    accepted_count = len(accepted_codes)
    
    # If all E/M codes were rejected, set a flag for potential retry
    if original_count > 0 and accepted_count == 0:
        logger.warning("All E/M codes were rejected - may trigger retry")
        state["all_em_rejected"] = True  # type: ignore
    else:
        state["all_em_rejected"] = False  # type: ignore

    return state


async def icd_validator_node(state: BillingState) -> BillingState:
    """Validate ICD-10 codes using format pattern validation.
    
    Since ICD-10 codes are not available in CSV files, we perform basic format
    validation using the ICD-10 pattern (letter + digits, optionally with a dot).
    """
    icd_candidates = state.get("billing_response", {}).get("ICD10_codes", [])
    state["validated_icd"] = []
    
    if not icd_candidates:
        logger.info("No ICD-10 code candidates to validate")
        return state
    
    accepted_codes = []
    rejected_codes = []
    
    logger.warning("ICD-10 validation: Full database validation not available. Using format pattern validation only.")
    
    for code_entry in icd_candidates:
        try:
            code = code_entry.get("code", "").strip().upper()
            if not code:
                logger.warning("Skipping ICD-10 entry with empty code")
                rejected_codes.append({"code": None, "reason": "empty code field"})
                continue
            
            # Validate against ICD-10 format pattern
            if ICD10_PATTERN.match(code):
                state["validated_icd"].append({
                    "code": code,
                    "description": code_entry.get("description", ""),
                    "original_description": code_entry.get("description", ""),
                    "validation_note": "Format validated only - full DB validation not available"
                })
                accepted_codes.append(code)
                logger.info(f"ICD-10 code '{code}' passed format validation: {code_entry.get('description', 'N/A')}")
            else:
                rejected_codes.append({"code": code, "reason": "Invalid ICD-10 format"})
                logger.warning(f"ICD-10 code '{code}' rejected - invalid format (expected: letter + digits, e.g., L70.0)")
                state.setdefault("validation_errors", []).append({
                    "type": "icd_validation",
                    "code": code,
                    "reason": "Invalid ICD-10 format"
                })
        except Exception as e:
            logger.error(f"Error validating ICD-10 code entry {code_entry}: {e}")
            rejected_codes.append({"code": code_entry.get("code"), "reason": f"Error: {e}"})
    
    logger.info(f"ICD-10 validation: {len(accepted_codes)} accepted, {len(rejected_codes)} rejected (format validation only)")
    if rejected_codes:
        logger.info(f"Rejected ICD-10 codes: {rejected_codes}")
    
    return state


def output_layer(state: BillingState) -> BillingState:
    """
    Final quality gate that filters and validates the final output.
    - Filters to only validated codes (CPT, E/M, and ICD-10)
    - Ensures CPT codes have linked ICD-10
    - Removes any codes with empty/null code field
    - Logs final accepted vs LLM original suggestions
    """
    billing_response = state.get("billing_response", {})
    superbill = state.get("superbill", {})
    billing_codes = superbill.get("billing_codes", {})

    # Get validated code sets for fast lookup
    validated_cpt_set = {c.get("proCode") for c in state.get("validated_cpt", []) if c.get("proCode")}
    validated_em_set = {e.get("enmCode") for e in state.get("validated_em", []) if e.get("enmCode")}
    validated_icd_set = {i.get("code") for i in state.get("validated_icd", []) if i.get("code")}

    # Original LLM suggestions
    original_cpt = billing_response.get("CPT_codes", [])
    original_em = billing_response.get("E_M_codes", [])
    original_icd = billing_response.get("ICD10_codes", [])

    final_rows = []
    codes_without_icd = []

    # Process CPT codes
    for cpt in original_cpt:
        code = cpt.get("code")
        if not code:
            logger.warning("Skipping CPT with empty code field in output layer")
            continue
            
        if code not in validated_cpt_set:
            logger.debug(f"CPT code '{code}' not in validated set - skipping")
            continue

        # Filter linked_icd to only validated ICD codes
        linked_icd = cpt.get("linked_icd10", [])
        validated_linked_icd = [icd for icd in linked_icd if icd in validated_icd_set]
        
        if not validated_linked_icd:
            codes_without_icd.append(code)
            logger.warning(f"CPT code '{code}' has no validated linked ICD-10 codes")

        final_rows.append({
            "procedure": cpt.get("description", ""),
            "code": code,
            "type": "CPT",
            "modifiers": cpt.get("modifiers", []),
            "dx_codes": validated_linked_icd,
            "qty": cpt.get("Quantity", cpt.get("quantity", 1)),
            "per_unit": cpt.get("chargePerUnit", 0),
        })

    # Process E/M codes
    for em in original_em:
        code = em.get("code")
        if not code:
            logger.warning("Skipping E/M with empty code field in output layer")
            continue
            
        if code not in validated_em_set:
            logger.debug(f"E/M code '{code}' not in validated set - skipping")
            continue

        # Filter linked_icd to only validated ICD codes
        linked_icd = em.get("linked_icd10", [])
        validated_linked_icd = [icd for icd in linked_icd if icd in validated_icd_set]
        
        if not validated_linked_icd:
            codes_without_icd.append(code)
            logger.warning(f"E/M code '{code}' has no validated linked ICD-10 codes")

        final_rows.append({
            "procedure": em.get("description", ""),
            "code": code,
            "type": "EM",
            "modifiers": em.get("modifiers", []),
            "dx_codes": validated_linked_icd,
            "qty": em.get("Quantity", em.get("quantity", 1)),
            "per_unit": "Yes",
        })

    # Apply per-unit charge configuration from validated CPT data
    cpt_config = {c.get("proCode"): c for c in state.get("validated_cpt", []) if c.get("proCode")}
    
    for row in final_rows:
        if row["code"] in cpt_config:
            charge_flag = cpt_config[row["code"]].get("chargePerUnit", 0)
            row["per_unit"] = "Yes" if charge_flag == 1 else "No"

    # Sort: CPT codes first, then E/M
    final_rows.sort(key=lambda x: (x["type"] != "CPT", x["code"]))

    # Log summary
    logger.info("=" * 50)
    logger.info("OUTPUT LAYER SUMMARY")
    logger.info("=" * 50)
    logger.info(f"LLM suggested: {len(original_cpt)} CPT, {len(original_em)} E/M, {len(original_icd)} ICD-10 codes")
    
    final_cpt_count = sum(1 for r in final_rows if r["type"] == "CPT")
    final_em_count = sum(1 for r in final_rows if r["type"] == "EM")
    validated_icd_count = len(state.get("validated_icd", []))
    logger.info(f"Final accepted: {final_cpt_count} CPT, {final_em_count} E/M, {validated_icd_count} ICD-10 codes")
    
    if codes_without_icd:
        logger.warning(f"Codes without linked ICD-10: {codes_without_icd}")
    
    # List accepted codes
    accepted_cpt = [r["code"] for r in final_rows if r["type"] == "CPT"]
    accepted_em = [r["code"] for r in final_rows if r["type"] == "EM"]
    accepted_icd = [i.get("code") for i in state.get("validated_icd", [])]
    logger.info(f"Accepted CPT codes: {accepted_cpt}")
    logger.info(f"Accepted E/M codes: {accepted_em}")
    logger.info(f"Accepted ICD-10 codes: {accepted_icd}")
    logger.info("=" * 50)

    # Store final filtered results back in state
    state["final_output"] = final_rows  # type: ignore
    
    # Also update the superbill with final filtered codes
    if "superbill" in state:
        state["superbill"]["final_cpt_codes"] = [r for r in final_rows if r["type"] == "CPT"]
        state["superbill"]["final_em_codes"] = [r for r in final_rows if r["type"] == "EM"]
        state["superbill"]["final_icd_codes"] = state.get("validated_icd", [])
        state["superbill"]["codes_without_icd_warning"] = codes_without_icd

    return state
