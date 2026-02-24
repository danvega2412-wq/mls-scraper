import os, json
from dotenv import load_dotenv
load_dotenv(dotenv_path='../.env')
from pinecone import Pinecone, ServerlessSpec

PINECONE_KEY = os.environ.get('PINECONE_API_KEY')
CLAUDE_KEY = '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'
INDEX_NAME = 'earl-audits'

def get_index():
    pc = Pinecone(api_key=PINECONE_KEY)
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print('Creating Pinecone index...')
        pc.create_index(
            name=INDEX_NAME,
            dimension=1536,
            metric='cosine',
            spec=ServerlessSpec(cloud='aws', region='us-east-1')
        )
        print('Index created.')
    return pc.Index(INDEX_NAME)

def get_embedding(text):
    import httpx
    with httpx.Client(timeout=30.0) as client:
        res = client.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key': CLAUDE_KEY, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': 'claude-sonnet-4-5', 'max_tokens': 10,
                  'messages': [{'role': 'user', 'content': 'embed: ' + text[:500]}]})
    return None

def save_approved_audit(mls, listing_data, report_text):
    import httpx, hashlib
    pc = Pinecone(api_key=PINECONE_KEY)
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        get_index()
    index = pc.Index(INDEX_NAME)
    combined = json.dumps(listing_data) + ' AUDIT: ' + report_text
    with httpx.Client(timeout=30.0) as client:
        res = client.post('https://api.openai.com/v1/embeddings',
            headers={'Authorization': 'Bearer ' + os.environ.get('OPENAI_API_KEY', ''),
                     'content-type': 'application/json'},
            json={'model': 'text-embedding-3-small', 'input': combined[:8000]})
        data = res.json()
        if 'data' not in data:
            print('Embedding error: ' + str(data))
            return False
        embedding = data['data'][0]['embedding']
    doc_id = 'audit_' + mls + '_' + hashlib.md5(report_text.encode()).hexdigest()[:8]
    index.upsert(vectors=[{
        'id': doc_id,
        'values': embedding,
        'metadata': {
            'mls': mls,
            'price': listing_data.get('price', ''),
            'dom': listing_data.get('dom', ''),
            'sqft': listing_data.get('sqft', ''),
            'city': listing_data.get('city', ''),
            'report': report_text[:2000]
        }
    }])
    print('Audit saved to Pinecone: ' + doc_id)
    return True

def get_similar_audits(listing_data, n=3):
    import httpx
    pc = Pinecone(api_key=PINECONE_KEY)
    existing = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in existing:
        return []
    index = pc.Index(INDEX_NAME)
    query_text = json.dumps(listing_data)
    with httpx.Client(timeout=30.0) as client:
        res = client.post('https://api.openai.com/v1/embeddings',
            headers={'Authorization': 'Bearer ' + os.environ.get('OPENAI_API_KEY', ''),
                     'content-type': 'application/json'},
            json={'model': 'text-embedding-3-small', 'input': query_text[:8000]})
        data = res.json()
        if 'data' not in data:
            return []
        embedding = data['data'][0]['embedding']
    results = index.query(vector=embedding, top_k=n, include_metadata=True)
    return [m['metadata']['report'] for m in results['matches'] if 'report' in m['metadata']]

if __name__ == '__main__':
    print('Setting up Pinecone index...')
    get_index()
    print('RAG system ready.')
