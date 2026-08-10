import sys
sys.path.insert(0, 'backend')

for m in ['models', 'document_processor', 'rag_engine', 'billing', 'ai_agent']:
    print(f"importing {m}...")
    try:
        __import__(m)
        print(f"  {m} OK")
    except Exception as e:
        print(f"  {m} FAILED: {e}")
