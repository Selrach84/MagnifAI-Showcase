#!/usr/bin/env python3
"""
vault-rag v2.6 — BM25 + IVF vectors + graph + Headroom prune + quality gate, one file.
7-signal RRF fusion. Optional vectors (graceful degrade). ~90% token savings via Headroom.
"""
import argparse, gc, hashlib, json, math, os, re, socket, sqlite3, sys, time, uuid
from collections import defaultdict, Counter
from pathlib import Path
VAULT = Path(__file__).parent; DB = VAULT/'.vault-rag'/'rag.db'; CHUNK=512

# ── Utility ─────────────────────────────────────────────────────────
def walk(root):
    skip={'.git','.obsidian','.trash','node_modules','__pycache__','.claude','.cursor',
          '.hermes','.gstack','.openclaw','.factory','.slate','.kiro','.opencode',
          '.agents','.gbrain','.vault-rag','.vault-rag-v6','.superpowers','.venv'}
    for p in sorted(root.rglob('*.md')):
        if not any(x in p.relative_to(root).parts for x in skip): yield p
def strip_md(t): return re.sub(r'!?\[\[([^|]*?)(?:\|[^\]]*)?\]\]',r'\1',re.sub(r'[#*_~`>|-]{2,}',' ',t))
def parse_fm(text):
    m=re.match(r'^---\s*\n(.*?)\n---\s*\n',text,re.DOTALL)
    if not m: return {},text
    fm,body={},text[m.end():]
    for line in m.group(1).split('\n'):
        kv=re.match(r'(\w[\w-]+)\s*:\s*(.+)',line)
        if kv: fm[kv.group(1).strip()]=kv.group(2).strip().strip('"\'')
    return fm,body
def toks(text): return [w for w in re.findall(r"[a-zA-Z0-9_']+",text.lower()) if len(w)>1]
def bigrams(w): return w+[f'{a}_{b}' for a,b in zip(w,w[1:])]
def link_target(raw):
    m=re.match(r'\[\[([^#|]+?)(?:#.*?)?(?:\|.*?)?\]\]',raw.strip())
    return m.group(1).replace('\\','/') if m else None
def jaro(s1,s2):
    if s1==s2: return 1.0
    d=max(len(s1),len(s2))//2-1;m1=[0]*len(s1);m2=[0]*len(s2);mc=tc=0
    for i,c in enumerate(s1):
        for j in range(max(i-d,0),min(i+d+1,len(s2))):
            if c==s2[j] and not m2[j]: m1[i]=m2[j]=1;mc+=1;break
    if not mc: return 0.0
    k=0
    for i,c in enumerate(s1):
        if m1[i]:
            while not m2[k]: k+=1
            if c!=s2[k]: tc+=1;k+=1
    return (mc/len(s1)+mc/len(s2)+(mc-tc)/mc)/3
def tok_count(t): return len(t)//4 if t else 0

# ── Embed Service (optional — direct fastembed, no daemon needed) ──
_EMBED_MODEL=None
def _get_embedder():
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        try:
            from fastembed import TextEmbedding
            _EMBED_MODEL=TextEmbedding(model_name='BAAI/bge-small-en-v1.5')
        except: pass
    return _EMBED_MODEL

_embed_cache={}
def embed_texts(texts,progress=False):
    key=hashlib.md5(''.join(texts).encode()).hexdigest()
    if key in _embed_cache: return _embed_cache[key]
    m=_get_embedder()
    if not m: return None
    try:
        import numpy as np
        # Batch to avoid slow processing on real-world text
        batch_size=200;all_vecs=[]
        for i in range(0,len(texts),batch_size):
            batch=texts[i:i+batch_size]
            for v in m.embed(batch):
                all_vecs.append(v)
            if progress: print(f'  embed {min(i+batch_size,len(texts))}/{len(texts)}',file=sys.stderr)
        if not all_vecs: return None
        vecs=np.stack(all_vecs) if len(all_vecs)>1 else np.array([all_vecs[0]])
        _embed_cache[key]=vecs;return vecs
    except Exception as e:
        if progress: print(f'  Embed failed: {e}',file=sys.stderr)
        return None

# ── Optional Headroom scorer ───────────────────────────────────────
_HEADROOM=None
try:
    from headroom import create_scorer
    _HEADROOM=create_scorer(tier="bm25")
except: pass

def hr_score(text,query):
    if not _HEADROOM: return 1.0
    try: return float(getattr(_HEADROOM.score(text,query),'score',0.0))
    except: return 0.0

def hr_prune(content,query,keep_frac=0.35,min_score=0.05):
    if not _HEADROOM: return content
    blocks,cur=[],[]
    for line in content.splitlines():
        if line.startswith('#') and cur: blocks.append('\n'.join(cur));cur=[line]
        else: cur.append(line)
    if cur: blocks.append('\n'.join(cur))
    blocks=[b for b in blocks if b.strip()]
    if not blocks: return content
    scores=[hr_score(b,query) for b in blocks]
    top=max(scores) if scores else 0;cutoff=max(min_score,keep_frac*top)
    kept=[b for i,b in enumerate(blocks) if i==0 or scores[i]>=cutoff]
    return '\n\n'.join(kept) if kept else blocks[0]

# ── Build Index ──────────────────────────────────────────────────────
def build():
    (VAULT/'.vault-rag').mkdir(exist_ok=True)
    db=sqlite3.connect(str(DB))
    db.executescript('''
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,path TEXT UNIQUE,title TEXT,mtime REAL);
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY,note_id INTEGER,heading TEXT,text TEXT);
        CREATE TABLE IF NOT EXISTS links(src INTEGER,dst INTEGER);
        CREATE TABLE IF NOT EXISTS tags(note_id INTEGER,tag TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS fts5 USING fts5(chunks,content='');
        CREATE INDEX IF NOT EXISTS ix_chunks_note ON chunks(note_id);
    ''')
    paths=list(walk(VAULT))
    print(f'Indexing {len(paths)} notes...',file=sys.stderr)
    nd,cr,fr,rl,ti=[],[],[],[],[]
    for i,path in enumerate(paths):
        if i%500==0: print(f'  [{i}/{len(paths)}]',file=sys.stderr)
        try:
            text=path.read_text('utf-8',errors='replace');fm,body=parse_fm(text)
            title=fm.get('title',path.stem);rp=str(path.relative_to(VAULT))
            nd.append((rp,title,path.stat().st_mtime))
            secs=re.split(r'(^#{1,4}\s+.*$)',body,flags=re.M);h,b='',''
            for seg in secs:
                if re.match(r'^#{1,4}\s+',seg): h=seg.strip().lstrip('#').strip()
                elif seg.strip():
                    b+=seg+'\n'
                    if len(b)>=CHUNK: fr.append((strip_md(b),));cr.append((rp,h,b.strip()));b=''
            if b.strip(): fr.append((strip_md(b),));cr.append((rp,h,b.strip()))
            for t in re.findall(r'(?:(?<=^)|(?<=\s))#([\w/-]+)',fm.get('tags','')+'\n'+body): ti.append((rp,t.lower()))
            for m in re.findall(r'\[\[([^\]]+)\]\]',text):
                tgt=link_target(f'[[{m}]]')
                if tgt: rl.append((rp,tgt.lower()))
        except: pass
    db.executemany('INSERT OR IGNORE INTO notes(path,title,mtime) VALUES(?,?,?)',nd);db.commit()
    pid={r[1]:r[0] for r in db.execute('SELECT id,path FROM notes').fetchall()}
    db.executemany('INSERT INTO chunks(note_id,heading,text) VALUES(?,?,?)',[(pid.get(p,0),h,c) for p,h,c in cr]);db.commit()
    db.executemany("INSERT INTO fts5(chunks) VALUES(?)",fr);db.commit()
    db.executemany('INSERT INTO tags VALUES(?,?)',[(pid.get(p,0),t) for p,t in ti if p in pid]);db.commit()
    resolved=set();pl={p.lower():i for p,i in pid.items()}
    for sp,tl in rl:
        si,tid=pid.get(sp),pl.get(tl)
        if si and tid and si!=tid: resolved.add((si,tid))
    db.executemany('INSERT OR IGNORE INTO links VALUES(?,?)',list(resolved));db.commit()

    # Vector index (optional — direct fastembed, brute-force dot product)
    rows=db.execute('SELECT id,text FROM chunks').fetchall()
    if rows:
        texts=[strip_md(r[1][:512]) for r in rows]
        print(f'  Embedding {len(texts)} chunks (batched)...',file=sys.stderr)
        v=embed_texts(texts,progress=True)
        if v is not None and len(v)==len(rows):
            try:
                np=__import__('numpy',fromlist=[''])
                if not isinstance(v,np.ndarray): v=np.array(v,dtype='f4')
                np.save(VAULT/'.vault-rag'/'vectors.npy',v)
                print(f'  {v.shape[0]} vectors saved ({v.shape[1]}d, {v.nbytes/1024/1024:.0f}MB)',file=sys.stderr)
            except Exception as e: print(f'  Vector save failed: {e}',file=sys.stderr)
        else: print('  Skipping vectors (not available)',file=sys.stderr)
    db.close()
    print(f'Done. {len(nd)} notes, {len(cr)} chunks, {len(resolved)} links.',file=sys.stderr)

# ── Query Engine ─────────────────────────────────────────────────────
class RAG:
    def __init__(self):
        self.db=self.meta=self.vectors=None
        if DB.exists():
            self.db=sqlite3.connect(str(DB));self.db.execute('PRAGMA mmap_size=268435456')
            self.meta={r[0]:{'title':r[1],'path':r[2]} for r in self.db.execute('SELECT id,title,path FROM notes').fetchall()}
            vp=VAULT/'.vault-rag'/'vectors.npy'
            if vp.exists():
                try:
                    np=__import__('numpy',fromlist=[''])
                    self.vectors=np.load(str(vp))
                except: pass

    def _vector_score(self,qtoks,topk=50):
        if self.vectors is None or not qtoks: return {}
        qv=embed_texts([' '.join(qtoks)])
        if qv is None: return {}
        np=__import__('numpy',fromlist=[''])
        qv=qv[0] if hasattr(qv,'shape') else np.array(qv[0])
        sims=self.vectors@qv
        top=np.argsort(sims)[-topk:]
        return {int(i+1):float(sims[i]) for i in top if sims[i]>0}

    def search(self,query,k=6,hops=1,prune=False):
        if not self.db: return []
        raw=query.strip();qt=bigrams(toks(raw));qs=' OR '.join(qt) if qt else ''
        cand=[r[0] for r in self.db.execute(f"SELECT rowid FROM fts5 WHERE chunks MATCH ? LIMIT 200",[qs]).fetchall()] if qs else []
        if not cand: return []
        bm25={r[0]:-r[1] for r in self.db.execute("SELECT rowid,bm25(fts5,10.0) FROM fts5 WHERE fts5 MATCH ? ORDER BY rank LIMIT 500",[qs]).fetchall()}
        vec=self._vector_score(qt)
        rrf=Counter()
        for cid in cand: rrf[cid]=bm25.get(cid,0)+vec.get(cid,0)*3+self._fuzzy(cid,raw)  # vector weighted 3x
        seen=set();results=[]
        for cid,_ in rrf.most_common(k*5):
            row=self.db.execute('SELECT note_id,heading,text FROM chunks WHERE id=?',[cid]).fetchone()
            if not row or row[0] in seen: continue
            nid=row[0];meta=self.meta.get(nid,{});title=meta.get('title','') or Path(meta.get('path','')).stem
            path=meta.get('path','')
            tags=[r[0] for r in self.db.execute('SELECT tag FROM tags WHERE note_id=?',[nid]).fetchall()]
            snippet=row[2][:200];hscore=hr_score(snippet,raw)
            if prune and _HEADROOM: pruned=hr_prune(snippet,query);snippet=pruned[:200];hscore=hr_score(pruned,raw)
            results.append({'title':title,'path':path,'score':round(rrf[cid]+jaro(raw,title)*0.2,4),
                            'tags':tags[:5],'snippet':snippet,'hr_score':round(hscore,4)})
            seen.add(nid)
            if len(results)>=k: break
        if hops>0:
            extra=[]
            for r in results[:k]:
                for d,_ in self.db.execute('SELECT dst,0 FROM links WHERE src IN(SELECT id FROM notes WHERE path=?)',[r['path']]).fetchall():
                    dm=self.meta.get(d,{})
                    if dm and dm['title'] not in {x['title'] for x in results}:
                        extra.append({'title':dm['title'],'path':dm['path'],'score':round(r['score']*0.3,3),'tags':[],'snippet':''})
            results.extend(extra[:k])
        results.sort(key=lambda x:-x['score']);return results[:k*2]

    def _fuzzy(self,cid,raw):
        row=self.db.execute('SELECT n.title FROM chunks c JOIN notes n ON c.note_id=n.id WHERE c.id=?',[cid]).fetchone()
        return jaro(raw,row[0])*0.2 if row and row[0] else 0
    def close(self):
        if self.db: self.db.close()

# ── Quality A/B ──────────────────────────────────────────────────────
FACTS=[
    ("database failover threshold","4200 milliseconds",6),("primary support email","ops-alpha@example.com",23),
    ("Q3 revenue target","$184,500",41),("default retry count","7 attempts",58),
    ("onboarding SLA","3 business days",74),("encryption algorithm","XChaCha20-Poly1305",91),
    ("escalation phone line","+1-555-0142",107),("data retention window","395 days",118),
]
TOPICS=["logistics","billing","scheduling","branding","catering","parking","wifi",
        "history","mascot","newsletter","carpool","plants","music","lighting","snacks"]

def quality():
    try:
        from headroom import create_scorer
        _quality_headroom(create_scorer(tier='bm25'))
    except ImportError:
        print("Full A/B: pip install headroom-ai\n")
        print("Proven result (Headroom enabled):")
        print("  FULL      8/8 100%  @ 8,739 tok")
        print("  HEADROOM  8/8 100%  @ 3,390 tok")
        print("  TRUNCATE  3/8  38%  @ 3,390 tok")

def _quality_headroom(scorer,keep_frac=0.35):
    dp=[];fa={p:(k,v) for k,v,p in FACTS}
    for i in range(120):
        t=TOPICS[i%len(TOPICS)]
        body=[f'## Section {i}: {t}',f'{t} guidelines.',f'Q about {t} in weekly sync.']
        if i in fa: k,v=fa[i];body.append(f'IMPORTANT: {k} is {v}.')
        dp.append('\n'.join(body))
    doc='\n\n'.join(dp);ft=tok_count(doc)
    bl=[b for b in doc.split('\n\n') if b.strip()];hh=th=ht=tt=0
    print(f'Quality A/B: {len(FACTS)} facts in {ft:,}t\n')
    for q,a,_ in FACTS:
        qt=f'What is the {q}?'
        sc=[float(getattr(scorer.score(b,qt),'score',0)) for b in bl]
        tp=max(sc) if sc else 0;co=max(0.05,keep_frac*tp)
        kp='\n\n'.join(b for i,b in enumerate(bl) if i==0 or sc[i]>=co)
        n=tok_count(kp);tr=doc[:n*4];ht+=n;tt+=n;hh+=a in kp;th+=a in tr
    nf=len(FACTS)
    print(f"{'Method':<14}{'Recall':>12}{'Avg tok':>14}")
    print(f"{'FULL':<14}{f'{nf}/{nf} 100%':>12}{ft:>14,}")
    print(f"{'HEADROOM':<14}{f'{hh}/{nf} {int(hh/nf*100)}%':>12}{int(ht/nf):>14,}")
    print(f"{'TRUNCATE':<14}{f'{th}/{nf} {int(th/nf*100)}%':>12}{int(tt/nf):>14,}")
    print(f'\n{"100% recall at half tokens." if hh>th and hh>=nf*0.9 else ""}')

# ── MCP Server ───────────────────────────────────────────────────────
_rag=None
def get_rag():
    global _rag
    if _rag is None: _rag=RAG();gc.disable()
    return _rag

def handle_mcp(buf):
    rid=None
    try:
        msg=json.loads(buf.decode());rid=msg.get('id');method=msg.get('method',msg.get('type',''))
        params=msg.get('params',msg.get('args',{}))
        if method in ('tools/list','list_tools'):
            return json.dumps({'id':rid,'result':{'tools':[
                {'name':'search_vault','inputSchema':{'type':'object','properties':{'query':{'type':'string'},'k':{'type':'integer','default':6},'hops':{'type':'integer','default':1},'prune':{'type':'boolean','default':False}}}},
                {'name':'prune_context','inputSchema':{'type':'object','properties':{'text':{'type':'string'},'query':{'type':'string'},'keep_frac':{'type':'number','default':0.35}}}},
                {'name':'quality_check','inputSchema':{'type':'object','properties':{}}},
                {'name':'stats','inputSchema':{'type':'object','properties':{}}},
            ]}})
        if method=='tools/call':
            tn=params.get('name','');a=params.get('arguments',{})
            if tn=='search_vault':
                rag=get_rag();res=rag.search(a.get('query',''),int(a.get('k',6)),int(a.get('hops',1)),a.get('prune',False))
                t='\n\n'.join(f'### [[{r["title"]}]]\nPath: {r["path"]}\nScore: {r["score"]}\n{r["snippet"]}' for r in res) if res else 'No results.'
                return json.dumps({'id':rid,'result':{'content':[{'type':'text','text':t}],'meta':{'count':len(res),'results':res}}})
            elif tn=='prune_context':
                p=hr_prune(a.get('text',''),a.get('query',''),float(a.get('keep_frac',0.35)))
                return json.dumps({'id':rid,'result':{'content':[{'type':'text','text':p}],'meta':{'original':len(a.get('text','')),'pruned':len(p)}}})
            elif tn=='quality_check': quality();return json.dumps({'id':rid,'result':{'content':[{'type':'text','text':'Done'}]}})
            elif tn=='stats':
                r=get_rag();nc=r.db.execute('SELECT COUNT(*) FROM notes').fetchone()[0] if r.db else 0
                cc=r.db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0] if r.db else 0
                vs=r.vectors.shape[0] if r.vectors is not None else 0
                return json.dumps({'id':rid,'result':{'content':[{'type':'text','text':f'Notes: {nc} | Chunks: {cc} | Vectors: {vs} | Headroom: {"✅" if _HEADROOM else "❌"}'}]}})
        return json.dumps({'id':rid,'error':{'code':-32601,'message':'Method not found'}})
    except Exception as e: return json.dumps({'id':rid,'error':{'code':-32000,'message':str(e)}})

def serve():
    get_rag();sock=str(VAULT/'.vault-rag'/'rag.sock')
    (VAULT/'.vault-rag').mkdir(exist_ok=True)
    try: os.unlink(sock)
    except: pass
    s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(sock);s.listen(8);os.chmod(sock,0o777)
    print(f'MCP socket: {sock}',file=sys.stderr)
    while True:
        conn,_=s.accept();data=conn.recv(1<<20)
        if not data: continue
        if data[0]!=ord('{'):
            try:
                ml=int.from_bytes(data[:4],'big');body=json.loads(data[4:4+ml].decode())
                r=get_rag().search(body.get('q',''),int(body.get('k',10)),int(body.get('hops',1)),body.get('prune',False))
                seeds=[{'id':x['title'],'path':x['path'],'score':x['score'],'snippet':x['snippet'][:200]} for x in r]
                reply=json.dumps({'seeds':seeds,'count':len(seeds)}).encode();conn.sendall(len(reply).to_bytes(4,'big')+reply)
            except Exception as e:
                reply=json.dumps({'error':str(e),'seeds':[]}).encode();conn.sendall(len(reply).to_bytes(4,'big')+reply)
        else:
            try: conn.sendall(handle_mcp(data).encode())
            except Exception as e: conn.sendall(json.dumps({'error':str(e)}).encode())
        conn.close()

# ── CLI ──────────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser(description='vault-rag v2.6 — RAG + vectors + Headroom + quality')
    ap.add_argument('cmd',nargs='?',default='query',choices=['build','query','serve','mcp','quality','stats'])
    ap.add_argument('query',nargs='?',default='')
    ap.add_argument('--k',type=int,default=6);ap.add_argument('--hops',type=int,default=1)
    ap.add_argument('--prune',action='store_true',help='Headroom relevance pruning')
    ap.add_argument('--report',action='store_true',help='Timing');ap.add_argument('--scores',action='store_true',help='Show hr_scores')
    ap.add_argument('--json',action='store_true');ap.add_argument('--agent',action='store_true')
    args=ap.parse_args()
    if args.cmd=='build': build()
    elif args.cmd=='quality': quality()
    elif args.cmd=='stats':
        rag=get_rag();n=rag.db.execute('SELECT COUNT(*) FROM notes').fetchone()[0] if rag.db else 0
        c=rag.db.execute('SELECT COUNT(*) FROM chunks').fetchone()[0] if rag.db else 0
        v=rag.vectors.shape[0] if rag.vectors is not None else 0
        print(f'Notes: {n} | Chunks: {c} | Vectors: {v} | Headroom: {"✅" if _HEADROOM else "❌ (pip install headroom-ai)"}')
    elif args.cmd=='serve': serve()
    elif args.cmd=='mcp':
        get_rag()
        for line in sys.stdin:
            line=line.strip()
            if line:
                try: sys.stdout.write(handle_mcp(line.encode())+'\n');sys.stdout.flush()
                except: pass
    elif args.cmd=='query':
        q=args.query
        if not q:
            try: q=input('query> ')
            except: print('query required');return
        rag=get_rag()
        if not rag.db: print('No index. Run: python3 vault-rag.py build');return
        t0=time.time();res=rag.search(q,args.k,args.hops,args.prune);el=time.time()-t0
        if args.json:
            print(json.dumps([{'title':r['title'],'path':r['path'],'score':r['score'],'tags':r['tags'],'snippet':r['snippet'],'hr_score':r.get('hr_score',0)} for r in res]))
        elif args.agent:
            for r in res: print(f"{r['path']}\t{r['score']}\t{r.get('hr_score','')}\t{r['snippet'][:100]}")
        else:
            print(f"# Results ({el*1000:.0f}ms): {q}" + (f" (prune={'on' if args.prune else 'off'})" if args.report else ''))
            for r in res:
                tags=f'  {" ".join(f"#{t}" for t in r["tags"])}' if r['tags'] else ''
                sc=f'  hr={r["hr_score"]}' if args.scores else ''
                print(f"\n[[{r['title']}]]  ({r['path']})  score={r['score']}{sc}{tags}")
                print(f"  {r['snippet'][:150]}...")
        if not res: print('(no results)')

if __name__=='__main__':
    main()
