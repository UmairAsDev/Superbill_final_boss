#!/usr/bin/env python3
"""
Script to set up pgvector tables in PostgreSQL (Neon) and populate them
with embeddings from local CSV files.

Usage: python scripts/populate_embeddings.py
"""

import csv
import os
import sys
import time
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv(PROJECT_ROOT / ".env")


# =============================================================================
# Configuration
# =============================================================================

# PostgreSQL (Neon) settings
PG_CONFIG = {
    "host": os.getenv("PGHOST"),
    "port": int(os.getenv("PGPORT", 5432)),
    "database": os.getenv("PGDATABASE"),
    "user": os.getenv("PGUSER"),
    "password": os.getenv("PGPASSWORD"),
    "sslmode": "require",
}

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# Batch settings
BATCH_SIZE = 50
RATE_LIMIT_SLEEP = 0.5


# =============================================================================
# Database Setup SQL
# =============================================================================

SETUP_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create procedures table
CREATE TABLE IF NOT EXISTS procedures (
    procedure_id BIGSERIAL PRIMARY KEY,
    cpt_code VARCHAR(10) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    deleted SMALLINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create ICD codes table
CREATE TABLE IF NOT EXISTS icd_codes (
    icd_code_id BIGSERIAL PRIMARY KEY,
    icd_code VARCHAR(10) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    is_billable BOOLEAN DEFAULT TRUE,
    deleted SMALLINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create E/M codes table
CREATE TABLE IF NOT EXISTS em_codes (
    em_code_id BIGSERIAL PRIMARY KEY,
    em_code VARCHAR(10) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    em_type VARCHAR(50),
    encounter_time INTEGER,
    em_level INTEGER,
    embedding vector(1536) NOT NULL,
    deleted SMALLINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Deduplicate procedures table (keep one row per cpt_code using ctid)
DELETE FROM procedures
WHERE ctid NOT IN (
    SELECT MAX(ctid) FROM procedures GROUP BY cpt_code
);

-- Deduplicate icd_codes table
DELETE FROM icd_codes
WHERE ctid NOT IN (
    SELECT MAX(ctid) FROM icd_codes GROUP BY icd_code
);

-- Deduplicate em_codes table
DELETE FROM em_codes
WHERE ctid NOT IN (
    SELECT MAX(ctid) FROM em_codes GROUP BY em_code
);

-- Ensure UNIQUE indexes exist (handles pre-existing tables without them)
CREATE UNIQUE INDEX IF NOT EXISTS idx_procedures_cpt_code_unique ON procedures (cpt_code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_icd_codes_icd_code_unique ON icd_codes (icd_code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_em_codes_em_code_unique ON em_codes (em_code);

-- Create HNSW indexes for fast similarity search
CREATE INDEX IF NOT EXISTS idx_procedures_embedding 
ON procedures USING hnsw(embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_icd_embedding 
ON icd_codes USING hnsw(embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_em_embedding 
ON em_codes USING hnsw(embedding vector_cosine_ops);
"""

# Upsert queries
UPSERT_PROCEDURE = """
INSERT INTO procedures (cpt_code, description, embedding)
VALUES (%s, %s, %s)
ON CONFLICT (cpt_code) DO UPDATE SET
    description = EXCLUDED.description,
    embedding = EXCLUDED.embedding,
    deleted = 0;
"""

UPSERT_ICD = """
INSERT INTO icd_codes (icd_code, description, embedding)
VALUES (%s, %s, %s)
ON CONFLICT (icd_code) DO UPDATE SET
    description = EXCLUDED.description,
    embedding = EXCLUDED.embedding,
    deleted = 0;
"""

UPSERT_EM = """
INSERT INTO em_codes (em_code, description, em_type, encounter_time, em_level, embedding)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (em_code) DO UPDATE SET
    description = EXCLUDED.description,
    em_type = EXCLUDED.em_type,
    encounter_time = EXCLUDED.encounter_time,
    em_level = EXCLUDED.em_level,
    embedding = EXCLUDED.embedding,
    deleted = 0;
"""


# =============================================================================
# Helper Functions
# =============================================================================

def get_pg_connection():
    """Create PostgreSQL connection."""
    print(f"Connecting to PostgreSQL at {PG_CONFIG['host']}...")
    conn = psycopg2.connect(**PG_CONFIG)
    print("PostgreSQL connection established.")
    return conn


def get_openai_client():
    """Create OpenAI client."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not found in environment")
    return OpenAI(api_key=OPENAI_API_KEY.strip())


def get_embeddings_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Get embeddings for a batch of texts."""
    response = client.embeddings.create(
        input=texts,
        model=EMBEDDING_MODEL
    )
    # Return embeddings in the same order as input
    return [item.embedding for item in response.data]


def format_embedding_for_pg(embedding: list[float]) -> str:
    """Format embedding list as PostgreSQL vector string."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


# =============================================================================
# Data Loading from CSV
# =============================================================================

def load_cpt_from_csv() -> list[tuple[str, str]]:
    """Load CPT codes from local CSV file."""
    codes = []
    seen = set()  # Deduplicate
    csv_path = os.path.join(PROJECT_ROOT, "data", "proCodeList.csv")
    print(f"Loading CPT codes from {csv_path}...")
    
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("deleted", "0")).strip() == "1":
                continue
            code = str(row.get("proCode", "")).strip()
            desc = str(row.get("codeDesc", "")).strip()
            if code and desc and code not in seen:
                seen.add(code)
                codes.append((code, desc))
    
    print(f"Found {len(codes)} CPT codes.")
    return codes


def load_em_from_csv() -> list[tuple[str, str, str, int, int]]:
    """Load E/M codes from local CSV file.
    
    Returns list of tuples: (code, description, em_type, encounter_time, em_level)
    """
    codes = []
    seen = set()  # Deduplicate
    csv_path = os.path.join(PROJECT_ROOT, "data", "enmCodeList.csv")
    print(f"Loading E/M codes from {csv_path}...")
    
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("deleted", "0")).strip() == "1":
                continue
            code = str(row.get("enmCode", "")).strip()
            desc = str(row.get("enmCodeDesc", "")).strip()
            em_type = str(row.get("enmType", "")).strip()
            try:
                encounter_time = int(row.get("encounterTime", 0))
            except (ValueError, TypeError):
                encounter_time = 0
            try:
                em_level = int(row.get("enmLevel", 0))
            except (ValueError, TypeError):
                em_level = 0
            
            if code and desc and code not in seen:
                seen.add(code)
                codes.append((code, desc, em_type, encounter_time, em_level))
    
    print(f"Found {len(codes)} E/M codes.")
    return codes


def get_common_dermatology_icd10() -> list[tuple[str, str]]:
    """Common dermatology ICD-10 codes for embedding population.
    Since MySQL is not accessible, use a curated dermatology code set."""
    return [
        # Skin cancers
        ("C43.0", "Malignant melanoma of lip"),
        ("C43.1", "Malignant melanoma of eyelid"),
        ("C43.2", "Malignant melanoma of ear"),
        ("C43.3", "Malignant melanoma of face"),
        ("C43.4", "Malignant melanoma of scalp and neck"),
        ("C43.5", "Malignant melanoma of trunk"),
        ("C43.6", "Malignant melanoma of upper limb"),
        ("C43.7", "Malignant melanoma of lower limb"),
        ("C43.9", "Malignant melanoma, unspecified"),
        ("C44.01", "Basal cell carcinoma of skin of lip"),
        ("C44.11", "Basal cell carcinoma of skin of eyelid"),
        ("C44.21", "Basal cell carcinoma of skin of ear"),
        ("C44.31", "Basal cell carcinoma of skin of face"),
        ("C44.41", "Basal cell carcinoma of scalp and neck"),
        ("C44.51", "Basal cell carcinoma of skin of trunk"),
        ("C44.61", "Basal cell carcinoma of skin of upper limb"),
        ("C44.71", "Basal cell carcinoma of skin of lower limb"),
        ("C44.02", "Squamous cell carcinoma of skin of lip"),
        ("C44.12", "Squamous cell carcinoma of skin of eyelid"),
        ("C44.22", "Squamous cell carcinoma of skin of ear"),
        ("C44.32", "Squamous cell carcinoma of skin of face"),
        ("C44.42", "Squamous cell carcinoma of scalp and neck"),
        ("C44.52", "Squamous cell carcinoma of skin of trunk"),
        ("C44.62", "Squamous cell carcinoma of skin of upper limb"),
        ("C44.72", "Squamous cell carcinoma of skin of lower limb"),
        # Premalignant
        ("L57.0", "Actinic keratosis"),
        ("D04.0", "Carcinoma in situ of skin of lip"),
        ("D04.3", "Carcinoma in situ of skin of face"),
        ("D04.5", "Carcinoma in situ of skin of trunk"),
        ("D04.6", "Carcinoma in situ of skin of upper limb"),
        ("D04.7", "Carcinoma in situ of skin of lower limb"),
        # Benign neoplasms
        ("D22.0", "Melanocytic nevi of lip"),
        ("D22.1", "Melanocytic nevi of eyelid"),
        ("D22.2", "Melanocytic nevi of ear"),
        ("D22.3", "Melanocytic nevi of face"),
        ("D22.4", "Melanocytic nevi of scalp and neck"),
        ("D22.5", "Melanocytic nevi of trunk"),
        ("D22.6", "Melanocytic nevi of upper limb"),
        ("D22.7", "Melanocytic nevi of lower limb"),
        ("D23.0", "Benign neoplasm of skin of lip"),
        ("D23.3", "Benign neoplasm of skin of face"),
        ("D23.5", "Benign neoplasm of skin of trunk"),
        ("D48.5", "Neoplasm of uncertain behavior of skin"),
        # Uncertain behavior
        ("D49.2", "Neoplasm of unspecified behavior of skin"),
        # Inflammatory
        ("L70.0", "Acne vulgaris"),
        ("L70.1", "Acne conglobata"),
        ("L40.0", "Psoriasis vulgaris"),
        ("L40.1", "Generalized pustular psoriasis"),
        ("L20.0", "Besnier prurigo (atopic dermatitis)"),
        ("L20.9", "Atopic dermatitis, unspecified"),
        ("L30.0", "Nummular dermatitis"),
        ("L30.9", "Dermatitis, unspecified"),
        ("L50.0", "Allergic urticaria"),
        ("L50.9", "Urticaria, unspecified"),
        # Infections
        ("B07.0", "Plantar wart"),
        ("B07.8", "Other viral warts"),
        ("B07.9", "Viral wart, unspecified"),
        ("B35.0", "Tinea barbae and tinea capitis"),
        ("B35.1", "Tinea unguium"),
        ("B35.3", "Tinea pedis"),
        ("B35.4", "Tinea corporis"),
        ("B36.0", "Pityriasis versicolor"),
        ("B00.1", "Herpesviral vesicular dermatitis"),
        ("B02.9", "Zoster without complications"),
        # Cysts and benign
        ("L72.0", "Epidermal cyst"),
        ("L72.1", "Pilar cyst"),
        ("L82.0", "Inflamed seborrheic keratosis"),
        ("L82.1", "Other seborrheic keratosis"),
        ("L91.0", "Hypertrophic scar / keloid"),
        ("L98.0", "Pyoderma gangrenosum"),
        # Pigmentary
        ("L81.0", "Postinflammatory hyperpigmentation"),
        ("L81.1", "Chloasma"),
        ("L80", "Vitiligo"),
        # Hair and nail
        ("L63.0", "Alopecia areata totalis"),
        ("L63.9", "Alopecia areata, unspecified"),
        ("L65.9", "Nonscarring hair loss, unspecified"),
        ("L66.9", "Cicatricial alopecia, unspecified"),
        # Rosacea
        ("L71.0", "Perioral dermatitis"),
        ("L71.1", "Rhinophyma"),
        ("L71.9", "Rosacea, unspecified"),
        # Other common
        ("L57.1", "Actinic reticuloid"),
        ("L56.0", "Drug phototoxic response"),
        ("L56.1", "Drug photoallergic response"),
        ("I10", "Essential hypertension"),
        ("E11.9", "Type 2 diabetes mellitus without complications"),
        ("Z12.83", "Encounter for screening for malignant neoplasm of skin"),
    ]


# =============================================================================
# Main Processing
# =============================================================================

def setup_pg_schema(pg_conn):
    """Create tables and indexes in PostgreSQL."""
    print("\nSetting up PostgreSQL schema...")
    with pg_conn.cursor() as cursor:
        cursor.execute(SETUP_SQL)
    pg_conn.commit()
    print("Schema setup complete.")


def process_cpt_codes(pg_conn, openai_client):
    """Process and insert CPT codes with embeddings."""
    print("\n" + "=" * 60)
    print("Processing CPT Codes")
    print("=" * 60)
    
    cpt_codes = load_cpt_from_csv()
    total = len(cpt_codes)
    
    if total == 0:
        print("No CPT codes to process.")
        return
    
    processed = 0
    errors = 0
    
    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = cpt_codes[i:i + BATCH_SIZE]
        
        try:
            # Prepare texts for embedding
            texts = [f"CPT {code}: {desc}" for code, desc in batch]
            
            # Get embeddings
            embeddings = get_embeddings_batch(openai_client, texts)
            
            # Insert into PostgreSQL
            with pg_conn.cursor() as cursor:
                for (code, desc), embedding in zip(batch, embeddings):
                    embedding_str = format_embedding_for_pg(embedding)
                    cursor.execute(UPSERT_PROCEDURE, (code, desc, embedding_str))
            
            pg_conn.commit()
            processed += len(batch)
            
            # Progress logging
            print(f"Processing CPT codes: {processed}/{total}...")
            
            # Rate limit handling
            if i + BATCH_SIZE < total:
                time.sleep(RATE_LIMIT_SLEEP)
                
        except Exception as e:
            errors += len(batch)
            print(f"Error processing batch at index {i}: {e}")
            pg_conn.rollback()
    
    print(f"CPT codes completed: {processed} processed, {errors} errors")


def process_icd_codes(pg_conn, openai_client):
    """Process and insert ICD-10 codes with embeddings."""
    print("\n" + "=" * 60)
    print("Processing ICD-10 Codes")
    print("=" * 60)
    
    icd_codes = get_common_dermatology_icd10()
    total = len(icd_codes)
    
    if total == 0:
        print("No ICD codes to process.")
        return
    
    processed = 0
    errors = 0
    
    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = icd_codes[i:i + BATCH_SIZE]
        
        try:
            # Prepare texts for embedding
            texts = [f"ICD-10 {code}: {desc}" for code, desc in batch]
            
            # Get embeddings
            embeddings = get_embeddings_batch(openai_client, texts)
            
            # Insert into PostgreSQL
            with pg_conn.cursor() as cursor:
                for (code, desc), embedding in zip(batch, embeddings):
                    embedding_str = format_embedding_for_pg(embedding)
                    cursor.execute(UPSERT_ICD, (code, desc, embedding_str))
            
            pg_conn.commit()
            processed += len(batch)
            
            # Progress logging
            print(f"Processing ICD codes: {processed}/{total}...")
            
            # Rate limit handling
            if i + BATCH_SIZE < total:
                time.sleep(RATE_LIMIT_SLEEP)
                
        except Exception as e:
            errors += len(batch)
            print(f"Error processing batch at index {i}: {e}")
            pg_conn.rollback()
    
    print(f"ICD codes completed: {processed} processed, {errors} errors")


def process_em_codes(pg_conn, openai_client):
    """Process and insert E/M codes with embeddings."""
    print("\n" + "=" * 60)
    print("Processing E/M Codes")
    print("=" * 60)
    
    em_codes = load_em_from_csv()
    total = len(em_codes)
    
    if total == 0:
        print("No E/M codes to process.")
        return
    
    processed = 0
    errors = 0
    
    # Process in batches
    for i in range(0, total, BATCH_SIZE):
        batch = em_codes[i:i + BATCH_SIZE]
        
        try:
            # Prepare texts for embedding
            # Include E/M type and level for better semantic matching
            texts = []
            for code, desc, em_type, encounter_time, em_level in batch:
                type_label = em_type.replace("Pat", " patient") if em_type else ""
                text = f"E/M {code}: {desc}"
                if type_label:
                    text += f" ({type_label})"
                if em_level:
                    text += f" level {em_level}"
                texts.append(text)
            
            # Get embeddings
            embeddings = get_embeddings_batch(openai_client, texts)
            
            # Insert into PostgreSQL
            with pg_conn.cursor() as cursor:
                for (code, desc, em_type, encounter_time, em_level), embedding in zip(batch, embeddings):
                    embedding_str = format_embedding_for_pg(embedding)
                    cursor.execute(UPSERT_EM, (code, desc, em_type, encounter_time, em_level, embedding_str))
            
            pg_conn.commit()
            processed += len(batch)
            
            # Progress logging
            print(f"Processing E/M codes: {processed}/{total}...")
            
            # Rate limit handling
            if i + BATCH_SIZE < total:
                time.sleep(RATE_LIMIT_SLEEP)
                
        except Exception as e:
            errors += len(batch)
            print(f"Error processing batch at index {i}: {e}")
            pg_conn.rollback()
    
    print(f"E/M codes completed: {processed} processed, {errors} errors")


def main():
    """Main entry point."""
    print("=" * 60)
    print("pgvector Embedding Population Script")
    print("=" * 60)
    
    pg_conn = None
    
    try:
        # Initialize connections
        openai_client = get_openai_client()
        pg_conn = get_pg_connection()
        
        # Step 1: Setup PostgreSQL schema
        setup_pg_schema(pg_conn)
        
        # Step 2: Process CPT codes from CSV
        process_cpt_codes(pg_conn, openai_client)
        
        # Step 3: Process ICD-10 codes (hardcoded dermatology codes)
        process_icd_codes(pg_conn, openai_client)
        
        # Step 4: Process E/M codes from CSV
        process_em_codes(pg_conn, openai_client)
        
        print("\n" + "=" * 60)
        print("Population complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise
        
    finally:
        # Cleanup connections
        if pg_conn:
            pg_conn.close()
            print("PostgreSQL connection closed.")


if __name__ == "__main__":
    main()
