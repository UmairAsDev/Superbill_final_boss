from pgdatabase.ingest import get_embedding


def build_cpt_query(proc):
    parts = [
        proc.get("type"),
        proc.get("method"),
        proc.get("location"),
    ]

    return " ".join(filter(None, parts)) + " dermatology procedure" 




import asyncio

async def async_get_embedding(text):
    return await asyncio.to_thread(get_embedding, text)




async def retrieve_cpt(proc, db):
    query_text = build_cpt_query(proc)

    embedding = await async_get_embedding(query_text)

    result = await db.execute(
        """
        SELECT cpt_code, description,
               embedding <=> :embedding AS distance
        FROM procedures
        WHERE deleted = 0
        ORDER BY embedding <=> :embedding
        LIMIT 5
        """,
        {"embedding": embedding}
    )

    rows = result.fetchall()

    return [
        {
            "code": r[0],
            "description": r[1],
            "score": 1 - r[2]  # similarity
        }
        for r in rows
    ]
    
    
async def retrieve_icd(dx_text, db):
    embedding = get_embedding(dx_text)

    result = await db.execute(
        """
        SELECT icd_code, description,
               embedding <=> :embedding AS distance
        FROM icd_codes
        ORDER BY embedding <=> :embedding
        LIMIT 3
        """,
        {"embedding": embedding}
    )

    rows = result.fetchall()

    return [
        {
            "code": r[0],
            "description": r[1],
            "score": 1 - r[2]
        }
        for r in rows
    ]

def filter_candidates(candidates, threshold=0.80):
    filtered = [c for c in candidates if c["score"] >= threshold]

    if filtered:
        return filtered

    # fallback: return best 1
    return candidates[:1] if candidates else []


async def retrieval_node(state, db):
    procedures = state["procedures"]
    diagnoses = state["diagnoses"]

    cpt_results = []
    for p in procedures:
        candidates = await retrieve_cpt(p, db)
        cpt_results.append({
            "procedure": p,
            "candidates": filter_candidates(candidates)
        })

    icd_results = []
    for d in diagnoses:
        candidates = await retrieve_icd(d, db)
        icd_results.append({
            "diagnosis": d,
            "candidates": filter_candidates(candidates)
        })

    state["retrieved"] = {
        "cpt": cpt_results,
        "icd": icd_results
    }

    return state