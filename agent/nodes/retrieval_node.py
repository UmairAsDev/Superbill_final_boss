"""Retrieval node for vector similarity search of CPT and ICD codes."""
from sqlalchemy import text
from loguru import logger

from sqldatabase.embedding import get_embedding, async_get_embedding
from sqldatabase.conn import pg_async_session


def build_cpt_query(proc):
    """Build query text from procedure information."""
    parts = [
        proc.get("type"),
        proc.get("method"),
        proc.get("location"),
    ]
    return " ".join(filter(None, parts)) + " dermatology procedure"


async def retrieve_cpt(proc, db):
    """Retrieve CPT code candidates using vector similarity search.
    
    Args:
        proc: Procedure dict with type, method, location keys
        db: Async database session
        
    Returns:
        List of candidate CPT codes with scores
    """
    query_text = build_cpt_query(proc)
    embedding = await async_get_embedding(query_text)

    result = await db.execute(
        text("""
        SELECT cpt_code, description,
               embedding <=> :embedding AS distance
        FROM procedures
        WHERE deleted = 0
        ORDER BY embedding <=> :embedding
        LIMIT 5
        """),
        {"embedding": str(embedding)}
    )

    rows = result.fetchall()

    return [
        {
            "code": r[0],
            "description": r[1],
            "score": 1 - r[2]  # Convert distance to similarity
        }
        for r in rows
    ]


async def retrieve_icd(dx_text, db):
    """Retrieve ICD code candidates using vector similarity search.
    
    Args:
        dx_text: Diagnosis text to search for
        db: Async database session
        
    Returns:
        List of candidate ICD codes with scores
    """
    embedding = await async_get_embedding(dx_text)

    result = await db.execute(
        text("""
        SELECT icd_code, description,
               embedding <=> :embedding AS distance
        FROM icd_codes
        ORDER BY embedding <=> :embedding
        LIMIT 3
        """),
        {"embedding": str(embedding)}
    )

    rows = result.fetchall()

    return [
        {
            "code": r[0],
            "description": r[1],
            "score": 1 - r[2]  # Convert distance to similarity
        }
        for r in rows
    ]


def filter_candidates(candidates, threshold=0.70):
    """Filter candidates by similarity threshold.
    
    Args:
        candidates: List of candidate dicts with 'score' key
        threshold: Minimum similarity score (default 0.70)
        
    Returns:
        Filtered list of candidates, or top 1 if none pass threshold
    """
    filtered = [c for c in candidates if c["score"] >= threshold]

    if filtered:
        return filtered

    # Fallback: return best 1
    return candidates[:1] if candidates else []


async def retrieval_node(state: dict) -> dict:
    """LangGraph node for retrieving reference CPT and ICD codes.
    
    This node extracts procedure descriptions and diagnosis text from the
    raw_note in state, performs vector similarity search against pgvector
    tables, and stores the results for the LLM to use.
    
    Args:
        state: Graph state containing raw_note and extracted data
        
    Returns:
        Updated state with retrieved_cpt and retrieved_icd
    """
    logger.info("Starting retrieval node for CPT and ICD codes")
    
    # Initialize results in case retrieval fails
    state["retrieved_cpt"] = []
    state["retrieved_icd"] = []
    
    try:
        # Extract procedures and diagnoses from state
        # These may come from prior extraction or from raw_note parsing
        procedures = state.get("procedures", [])
        diagnoses = state.get("diagnoses", [])
        
        # If no structured data, try to extract from raw_note
        raw_note = state.get("raw_note", "")
        if not procedures and not diagnoses and raw_note:
            logger.info("No structured data found, will rely on LLM extraction")
            # Let the LLM handle extraction, but we can still add context
            state["retrieval_context"] = "No pre-extracted procedures/diagnoses available for retrieval"
            return state
        
        async with pg_async_session() as db:
            # Retrieve CPT codes for each procedure
            cpt_results = []
            for proc in procedures:
                try:
                    candidates = await retrieve_cpt(proc, db)
                    filtered = filter_candidates(candidates)
                    cpt_results.append({
                        "procedure": proc,
                        "candidates": filtered
                    })
                    logger.debug(f"Retrieved {len(filtered)} CPT candidates for procedure: {proc}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve CPT for procedure {proc}: {e}")
                    cpt_results.append({
                        "procedure": proc,
                        "candidates": [],
                        "error": str(e)
                    })
            
            # Retrieve ICD codes for each diagnosis
            icd_results = []
            for dx in diagnoses:
                try:
                    # Handle both string diagnoses and dict diagnoses
                    dx_text = dx if isinstance(dx, str) else dx.get("description", str(dx))
                    candidates = await retrieve_icd(dx_text, db)
                    filtered = filter_candidates(candidates)
                    icd_results.append({
                        "diagnosis": dx,
                        "candidates": filtered
                    })
                    logger.debug(f"Retrieved {len(filtered)} ICD candidates for diagnosis: {dx_text}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve ICD for diagnosis {dx}: {e}")
                    icd_results.append({
                        "diagnosis": dx,
                        "candidates": [],
                        "error": str(e)
                    })
            
            state["retrieved_cpt"] = cpt_results
            state["retrieved_icd"] = icd_results
            
            # Build context for LLM to use reference codes
            context_parts = []
            if cpt_results:
                cpt_context = "Reference CPT codes:\n"
                for r in cpt_results:
                    for c in r.get("candidates", []):
                        cpt_context += f"  - {c['code']}: {c['description']} (score: {c['score']:.2f})\n"
                context_parts.append(cpt_context)
            
            if icd_results:
                icd_context = "Reference ICD codes:\n"
                for r in icd_results:
                    for c in r.get("candidates", []):
                        icd_context += f"  - {c['code']}: {c['description']} (score: {c['score']:.2f})\n"
                context_parts.append(icd_context)
            
            if context_parts:
                state["retrieval_context"] = "\n".join(context_parts)
                logger.info(f"Added retrieval context with {len(cpt_results)} CPT and {len(icd_results)} ICD lookups")
            
    except Exception as e:
        # Handle errors gracefully - don't crash the graph
        error_msg = str(e)
        
        # Check for common pgvector table errors
        if "does not exist" in error_msg.lower() or "relation" in error_msg.lower():
            logger.warning(f"pgvector tables may not exist yet: {error_msg}")
            state["retrieval_context"] = "Vector search tables not available - proceeding without retrieval"
        else:
            logger.error(f"Retrieval node error: {error_msg}")
            state["retrieval_context"] = f"Retrieval failed: {error_msg}"
        
        # Continue pipeline without retrieval rather than crashing
        logger.info("Continuing pipeline without retrieval results")
    
    logger.info("Retrieval node completed")
    return state
