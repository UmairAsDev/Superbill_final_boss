import logging
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from sqldatabase.sqldb import async_db_session
from sqlalchemy import text
from config.schema import BillingState
from typing import List, Dict, Any
from loguru import logger
logger = logging.getLogger("superbill_nodes")





def normalization_node(state: BillingState) -> BillingState:
    """
    Normalize LLM output so downstream nodes have consistent keys.
    Ensures lists/dicts are never None.
    """
    raw = state.get("billing_response", {})

    state["billing_response"] = {
        "CPT_codes": raw.get("CPT_codes") or [],
        "E_M_codes": raw.get("E_M_codes") or [],
        "ICD10_codes": raw.get("ICD10_codes") or [],
        "procedure_details": raw.get("procedure_details") or {},
    }

    return state



async def cpt_validator_node(state: BillingState) -> BillingState:
    """
    Validate CPT codes against database.
    Handles LLM dict output, exceptions, and single async session.
    """
    cpt_candidates: List[Dict[str, Any]] = state.get("billing_response", {}).get("CPT_codes", [])
    state["validated_cpt"] = []

    if not cpt_candidates:
        return state

    try:
        async with async_db_session() as db:
            for code_entry in cpt_candidates:
                code = code_entry.get("code")
                if not code:
                    continue  

                result = await db.execute(
                    text(
                        "SELECT * FROM proCodeList ccl WHERE ccl.proCode = :code AND ccl.deleted = 0"
                    ),
                    {"code": code},
                )
                row = result.fetchone()
                if row:
                    state["validated_cpt"].append({
                        "proCode": row[2],
                        "codeDesc": row[3],
                        "minQty": row[5],
                        "maxQty": row[6],
                        "minSize": row[7],
                        "maxSize": row[8],
                        "chargePerUnit": row[9],
                        "billWithIntEM": row[10],
                        "billWithFUEM": row[11],
                        "leftRightSepration": row[12],
                        "billAlone": row[13],
                        "splitInMultipleVisits": row[15],
                        "effectiveSince": row[16]
                    })

    except Exception as e:
        logger.error(f"CPT validator node failed: {e}")

    return state



async def em_validator_node(state: BillingState) -> BillingState:
    """
    Validate E/M codes against database.
    Handles dict input, exceptions, and single async session.
    """
    em_candidates: List[Dict[str, Any]] = state.get("billing_response", {}).get("E_M_codes", [])
    state["validated_em"] = []

    if not em_candidates:
        return state

    try:
        async with async_db_session() as db:
            for code_entry in em_candidates:
                code = code_entry.get("code")
                if not code:
                    continue  

                result = await db.execute(
                    text(
                        "SELECT * FROM enmCodeList ecl WHERE ecl.enmCode = :code AND ecl.deleted = 0"
                    ),
                    {"code": code},
                )
                row = result.fetchone()
                if row:
                    state["validated_em"].append({
                        "enmCode": row[1],
                        "enmCodeDesc": row[2],
                        "enmType": row[3],
                        "facilityCode": row[5],
                        "enmLevel": row[6]
                    })

    except Exception as e:
        logger.error(f"E/M validator node failed: {e}")

    return state




def output_layer(state: BillingState) -> BillingState:
    """
    Final node to prepare output.
    Can be extended for additional formatting or data enrichment.
    """
    return state