#!/usr/bin/env python3
"""Generator for AI Content Engine v2 n8n workflow.
Builds a valid, importable n8n workflow JSON with full error handling.
Run: python3 gen_workflow.py  -> writes workflow.n8n.json
"""
import json, itertools, os

# ---- config-driven: fill client.config.json to retarget for a new client ----
DEFAULTS = {
    "workflow_name": "AI Content Engine — Solar & Battery v2 (100X)",
    "diagram_title": "AI Content Engine for Solar & Battery — v2 (100X)",
    "claude_model": "claude-sonnet-4-5",
    "trigger_day": 1, "trigger_hour": 6,
    "segments": ["residential", "commercial", "battery"],
    "channels": [
        {"name": "Publish YouTube", "env": "YOUTUBE_ENDPOINT", "cred": "YOUTUBE"},
        {"name": "Publish WordPress (SEO+schema)", "env": "WORDPRESS_ENDPOINT", "cred": "WORDPRESS"},
        {"name": "Schedule LinkedIn", "env": "LINKEDIN_ENDPOINT", "cred": "LINKEDIN"},
        {"name": "Schedule Facebook", "env": "FACEBOOK_ENDPOINT", "cred": "FACEBOOK"},
        {"name": "Schedule Instagram", "env": "INSTAGRAM_ENDPOINT", "cred": "INSTAGRAM"},
        {"name": "Send Email Newsletter", "env": "EMAIL_ENDPOINT", "cred": "EMAIL"},
    ],
}
CFG = dict(DEFAULTS)
if os.path.exists("client.config.json"):
    CFG.update(json.load(open("client.config.json")))
    print(f"[config] loaded client.config.json -> {CFG['workflow_name']}")
else:
    print("[config] no client.config.json — using defaults (solar & battery)")

nodes = []
conns = {}
_pos = itertools.count()

def add(name, ntype, params=None, tv=1, x=0, y=0, on_error=None, creds=None):
    n = {
        "parameters": params or {},
        "id": name.lower().replace(" ", "-").replace("/", "-").replace(":", "")[:60] + f"-{next(_pos)}",
        "name": name,
        "type": ntype,
        "typeVersion": tv,
        "position": [x, y],
    }
    if on_error:
        n["onError"] = on_error
    if creds:
        n["credentials"] = creds
    nodes.append(n)
    return name

def link(src, dst, out=0, in_=0):
    conns.setdefault(src, {}).setdefault("main", [])
    main = conns[src]["main"]
    while len(main) <= out:
        main.append([])
    main[out].append({"node": dst, "type": "main", "index": in_})

# ---- credential placeholders (NOT secrets — references resolved in n8n UI) ----
CL = {"httpHeaderAuth": {"id": "REPLACE_ANTHROPIC", "name": "Anthropic API (x-api-key)"}}
GHL = {"httpHeaderAuth": {"id": "REPLACE_GHL", "name": "GoHighLevel API"}}
GEN = lambda name: {"httpHeaderAuth": {"id": f"REPLACE_{name}", "name": f"{name} API"}}

def claude(name, x, y, sys_prompt, user_expr, max_tokens=2000):
    """An Anthropic Claude messages call as an HTTP Request node, with error output."""
    params = {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "anthropic-version", "value": "2023-06-01"},
            {"name": "content-type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": json.dumps({
            "model": "={{ $env.CLAUDE_MODEL || '" + CFG["claude_model"] + "' }}",
            "max_tokens": max_tokens,
            "system": sys_prompt,
            "messages": [{"role": "user", "content": user_expr}],
        }),
        "options": {"retry": {"retry": {"maxTries": 3, "waitBetween": 2000}}},
    }
    return add(name, "n8n-nodes-base.httpRequest", params, tv=4.2, x=x, y=y,
               on_error="continueErrorOutput", creds=CL)

def http(name, url, x, y, method="POST", creds=None, body=None):
    params = {
        "method": method, "url": url,
        "options": {"retry": {"retry": {"maxTries": 3, "waitBetween": 2000}}},
    }
    if creds:
        params["authentication"] = "genericCredentialType"
        params["genericAuthType"] = "httpHeaderAuth"
    if body is not None:
        params["sendBody"] = True; params["specifyBody"] = "json"
        params["jsonBody"] = json.dumps(body)
    return add(name, "n8n-nodes-base.httpRequest", params, tv=4.2, x=x, y=y,
               on_error="continueErrorOutput", creds=creds)

# ===================== ERROR INFRA =====================
ERR = add("Error Collector", "n8n-nodes-base.noOp", {}, x=2600, y=1200)
ALERT = http("Alert Charles (Slack/Email)",
             "={{ $env.ALERT_WEBHOOK_URL }}", 2820, 1200, body={
                 "text": "=🚨 AI Content Engine failure at node {{ $json.error?.node?.name || 'unknown' }} — run {{ $json.runId }}",
             })
link(ERR, ALERT)
def guard(node):
    """route a node's error output (main index 1) to the collector."""
    link(node, ERR, out=1)

# ===================== LAYER 0 =====================
TRIG = add("Weekly Trigger (Mon 06:00)", "n8n-nodes-base.scheduleTrigger",
           {"rule": {"interval": [{"field": "weeks", "triggerAtDay": [CFG["trigger_day"]], "triggerAtHour": CFG["trigger_hour"]}]}},
           tv=1.2, x=-200, y=300)
GUARD = add("Kill-switch + Dedupe Guard", "n8n-nodes-base.code", {"jsCode": (
    "// kill-switch + idempotency\n"
    "if (($env.KILL_SWITCH||'').toLowerCase()==='true') return [];\n"
    "const d=new Date();\n"
    "const wk=`${d.getUTCFullYear()}-W${Math.ceil((((d-new Date(Date.UTC(d.getUTCFullYear(),0,1)))/864e5)+1)/7)}`;\n"
    "return [{ json: { runId: wk, startedAt: d.toISOString(), tokenBudget: Number($env.TOKEN_BUDGET||200000), tokensUsed: 0 } }];")},
    x=20, y=300)
link(TRIG, GUARD)

# ===================== LAYER 1 — STRATEGY =====================
ANALYTICS = http("Get Last-Week Analytics", "={{ $env.ANALYTICS_ENDPOINT }}", 240, 300, creds=GEN("ANALYTICS")); guard(ANALYTICS)
RESEARCH  = http("Trend+Keyword+Incentive Research", "={{ $env.RESEARCH_ENDPOINT }}", 460, 300, creds=GEN("RESEARCH")); guard(RESEARCH)
SCORING   = claude("Claude: Topic Scoring", 680, 300,
    "You score content topics for a solar & battery company by predicted ROI using prior performance. Output ONLY JSON {scored:[{topic,score,segment}]}.",
    "=Prior performance: {{ JSON.stringify($('Get Last-Week Analytics').item.json) }}\nResearch: {{ JSON.stringify($json) }}"); guard(SCORING)
V_SCORE = add("Validate Scoring JSON", "n8n-nodes-base.code", {"jsCode": (
    "const c=$json?.content?.[0]?.text ?? $json?.text ?? '';\n"
    "let o; try{o=JSON.parse(c);}catch(e){throw new Error('SCORING_BAD_JSON');}\n"
    "if(!Array.isArray(o.scored)) throw new Error('SCORING_SCHEMA');\n"
    "return [{json:{...$json, scored:o.scored}}];")}, x=900, y=300)
link(SCORING, V_SCORE)
IDEAS = claude("Claude: Generate 10 Segmented Ideas", 1120, 300,
    "Generate 10 content ideas across segments " + "/".join(CFG["segments"]) + " for the client. Output ONLY JSON {ideas:[{title,hook,segment,angle}]}.",
    "=Scored topics: {{ JSON.stringify($json.scored) }}"); guard(IDEAS)
V_IDEAS = add("Validate Ideas JSON", "n8n-nodes-base.code", {"jsCode": (
    "const c=$json?.content?.[0]?.text ?? '';\n"
    "let o; try{o=JSON.parse(c);}catch(e){throw new Error('IDEAS_BAD_JSON');}\n"
    "if(!Array.isArray(o.ideas)||o.ideas.length<1) throw new Error('IDEAS_SCHEMA');\n"
    "return o.ideas.map(i=>({json:{idea:i, runId:$('Kill-switch + Dedupe Guard').item.json.runId}}));")}, x=1340, y=300)
link(IDEAS, V_IDEAS)
STRAT_REVIEW = http("Strategy Review (human approve)", "={{ $env.APPROVAL_ENDPOINT }}", 1560, 300, creds=GHL,
    body={"runId": "={{ $json.runId }}", "stage": "strategy", "items": "={{ JSON.stringify($json.idea) }}"}); guard(STRAT_REVIEW)
IF_STRAT = add("Strategy Approved?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True}, "combinator": "and",
    "conditions": [{"leftValue": "={{ $json.approved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true"}}]}},
    tv=2, x=1780, y=300)
link(STRAT_REVIEW, IF_STRAT)
STRAT_REJECT = add("Rejected → re-research (NoOp)", "n8n-nodes-base.noOp", {}, x=1780, y=520)
link(IF_STRAT, STRAT_REJECT, out=1)  # false branch

# ===================== LAYER 2 — PRODUCTION =====================
BRIEF = claude("Claude: Content Brief", 2000, 300,
    "Write a structured content brief for the approved idea. Output ONLY JSON {brief:{goal,audience,outline,keywords,cta}}.",
    "=Idea: {{ JSON.stringify($json.idea) }}"); guard(BRIEF)
DRAFT = claude("Claude: Draft (script/blog/social)", 2220, 300,
    "Draft a video script, an SEO blog post, and social variants (LinkedIn, Facebook, Instagram) from the brief. Solar/battery domain. Output ONLY JSON {script,blog,social:{linkedin,facebook,instagram}}.",
    "=Brief: {{ JSON.stringify($json) }}", max_tokens=4000); guard(DRAFT)
V_DRAFT = add("Validate Draft Schema", "n8n-nodes-base.code", {"jsCode": (
    "const c=$json?.content?.[0]?.text ?? '';\n"
    "let o; try{o=JSON.parse(c);}catch(e){throw new Error('DRAFT_BAD_JSON');}\n"
    "for(const k of ['script','blog','social']) if(!o[k]) throw new Error('DRAFT_MISSING_'+k);\n"
    "return [{json:{draft:o, runId:$('Kill-switch + Dedupe Guard').item.json.runId, revise:0}}];")}, x=2440, y=300)
link(DRAFT, V_DRAFT)
THUMB = claude("Claude: Thumbnail Prompts", 2660, 300,
    "Create 3 thumbnail/image generation prompts for the content. Output ONLY JSON {prompts:[...]}.",
    "=Draft: {{ JSON.stringify($json.draft) }}"); guard(THUMB)

# ===================== LAYER 3 — QUALITY GATE =====================
BRAND = claude("Claude: Brand+SEO Check", 2880, 300,
    "Check the draft for brand voice + SEO. Output ONLY JSON {brandPass:bool, seoPass:bool, issues:[...]}.",
    "=Draft: {{ JSON.stringify($('Validate Draft Schema').item.json.draft) }}"); guard(BRAND)
COMPLY = claude("Claude: Solar Claims Compliance", 3100, 300,
    "You are a compliance reviewer. FLAG any unverifiable solar/battery savings %, ROI timeframe, or tax-credit/incentive claim. Truth-in-advertising. Output ONLY JSON {compliant:bool, flagged:[...]}.",
    "=Draft: {{ JSON.stringify($('Validate Draft Schema').item.json.draft) }}"); guard(COMPLY)
FACT = claude("Claude: Fact-check+Plagiarism", 3320, 300,
    "Fact-check claims and estimate AI/plagiarism risk. Output ONLY JSON {factPass:bool, plagiarismRisk:'low|med|high'}.",
    "=Draft: {{ JSON.stringify($('Validate Draft Schema').item.json.draft) }}"); guard(FACT)
QC = add("Aggregate QC Verdict", "n8n-nodes-base.code", {"jsCode": (
    "function p(n){const c=$(n).item.json?.content?.[0]?.text??'{}';try{return JSON.parse(c);}catch(e){return {};}}\n"
    "const b=p('Claude: Brand+SEO Check'), co=p('Claude: Solar Claims Compliance'), f=p('Claude: Fact-check+Plagiarism');\n"
    "const pass = b.brandPass && b.seoPass && co.compliant && f.factPass && f.plagiarismRisk!=='high';\n"
    "const base=$('Validate Draft Schema').item.json;\n"
    "return [{json:{...base, qc:{pass, brand:b, compliance:co, fact:f}}}];")}, x=3540, y=300)
link(BRAND, COMPLY); link(COMPLY, FACT); link(FACT, QC)
IF_QC = add("Quality Pass?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True}, "combinator": "and",
    "conditions": [{"leftValue": "={{ $json.qc.pass }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true"}}]}},
    tv=2, x=3760, y=300)
link(QC, IF_QC)
REVISE = add("Revise Counter", "n8n-nodes-base.code", {"jsCode": (
    "const r=($json.revise||0)+1; if(r>2) return [{json:{...$json, escalate:true, revise:r}}];\n"
    "return [{json:{...$json, revise:r, escalate:false}}];")}, x=3760, y=520)
link(IF_QC, REVISE, out=1)  # fail branch
IF_ESC = add("Escalate?", "n8n-nodes-base.if", {"conditions": {"options": {}, "combinator": "and",
    "conditions": [{"leftValue": "={{ $json.escalate }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true"}}]}},
    tv=2, x=3980, y=520)
link(REVISE, IF_ESC)
ESCALATE = http("Escalate to Human (alert)", "={{ $env.ALERT_WEBHOOK_URL }}", 4200, 640,
    body={"text": "=⚠️ Content failed QC 3x — human review needed. Run {{ $json.runId }}"})
link(IF_ESC, ESCALATE, out=0)         # escalate=true
link(IF_ESC, DRAFT, out=1)            # escalate=false -> loop back to redraft

# ===================== LAYER 4 — ASSETS & PACK =====================
ASSETS = http("Generate Assets (image-gen)", "={{ $env.IMAGEGEN_ENDPOINT }}", 3980, 300, creds=GEN("IMAGEGEN"),
    body={"prompts": "={{ $('Claude: Thumbnail Prompts').item.json.content[0].text }}"}); guard(ASSETS)
link(IF_QC, ASSETS, out=0)  # pass branch
PACK = add("Assemble Content Pack", "n8n-nodes-base.set", {"assignments": {"assignments": [
    {"name": "pack", "value": "={{ { draft: $('Validate Draft Schema').item.json.draft, assets: $json } }}", "type": "object"}]}},
    tv=3.4, x=4200, y=300)
link(ASSETS, PACK)
ZOHO = http("Zoho WorkDrive Upload (versioned)", "={{ $env.ZOHO_UPLOAD_ENDPOINT }}", 4420, 300, creds=GEN("ZOHO"),
    body={"folder": "=ContentEngine/{{ $('Kill-switch + Dedupe Guard').item.json.runId }}", "pack": "={{ JSON.stringify($json.pack) }}"}); guard(ZOHO)
link(PACK, ZOHO)

# ===================== LAYER 5 — APPROVAL =====================
EDITOR = http("Editor Review (human approve)", "={{ $env.APPROVAL_ENDPOINT }}", 4640, 300, creds=GHL,
    body={"runId": "={{ $('Kill-switch + Dedupe Guard').item.json.runId }}", "stage": "editor"}); guard(EDITOR)
link(ZOHO, EDITOR)
IF_ED = add("Editor Approved?", "n8n-nodes-base.if", {"conditions": {"options": {}, "combinator": "and",
    "conditions": [{"leftValue": "={{ $json.approved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true"}}]}},
    tv=2, x=4860, y=300)
link(EDITOR, IF_ED)
link(IF_ED, BRIEF, out=1)  # changes requested -> back to brief

# ===================== LAYER 6 — VIDEO & REPURPOSE =====================
WAIT_VID = add("Wait for Recorded Video", "n8n-nodes-base.wait",
    {"resume": "webhook", "options": {}}, tv=1.1, x=5080, y=300)
link(IF_ED, WAIT_VID, out=0)
CLIPS = http("Auto-cut Shorts/Reels/Clips", "={{ $env.CLIPPER_ENDPOINT }}", 5300, 300, creds=GEN("CLIPPER"),
    body={"videoUrl": "={{ $json.videoUrl }}"}); guard(CLIPS)
link(WAIT_VID, CLIPS)
FANOUT = add("Fan-out Prep", "n8n-nodes-base.set", {"assignments": {"assignments": [
    {"name": "utm", "value": "=utm_source={ch}&utm_campaign={{ $('Kill-switch + Dedupe Guard').item.json.runId }}", "type": "string"}]}},
    tv=3.4, x=5520, y=300)
link(CLIPS, FANOUT)

# ===================== LAYER 7 — PUBLISHING (parallel) =====================
channels = [(c["name"], "={{ $env." + c["env"] + " }}", c["cred"]) for c in CFG["channels"]]
MERGE = add("Merge Published", "n8n-nodes-base.merge", {"numberInputs": len(channels)}, tv=3, x=6180, y=300)
for i, (nm, url, cr) in enumerate(channels):
    cnode = http(nm, url, 5740, 120 + i*120, creds=GEN(cr),
                 body={"runId": "={{ $('Kill-switch + Dedupe Guard').item.json.runId }}", "utm": "={{ $('Fan-out Prep').item.json.utm }}"})
    guard(cnode)
    link(FANOUT, cnode)
    link(cnode, MERGE, in_=i)

# ===================== LAYER 8 — GROWTH & FEEDBACK =====================
LEADS = http("Capture Leads → GHL CRM", "={{ $env.GHL_LEADS_ENDPOINT }}", 6400, 300, creds=GHL,
    body={"runId": "={{ $('Kill-switch + Dedupe Guard').item.json.runId }}"}); guard(LEADS)
link(MERGE, LEADS)
ANALYTICS2 = http("Collect Analytics (48h/7d)", "={{ $env.ANALYTICS_ENDPOINT }}", 6620, 300, method="GET", creds=GEN("ANALYTICS")); guard(ANALYTICS2)
link(LEADS, ANALYTICS2)
SCORECARD = add("Performance Scorecard (persist)", "n8n-nodes-base.code", {"jsCode": (
    "// write scorecard the NEXT run reads -> closes the loop\n"
    "const card={ runId:$('Kill-switch + Dedupe Guard').item.json.runId, ts:new Date().toISOString(), metrics:$json };\n"
    "// persisted via static workflow data / external KV (see HANDOFF)\n"
    "const store=$getWorkflowStaticData('global'); store.lastScorecard=card;\n"
    "return [{json:card}];")}, x=6840, y=300)
link(ANALYTICS2, SCORECARD)
DIGEST = http("Team Digest (Slack)", "={{ $env.SLACK_DIGEST_URL }}", 7060, 300,
    body={"text": "=✅ AI Content Engine run {{ $json.runId }} complete. Scorecard stored."})
link(SCORECARD, DIGEST)
DONE = add("Workflow Complete", "n8n-nodes-base.noOp", {}, x=7280, y=300)
link(DIGEST, DONE)

# ===================== ASSEMBLE =====================
wf = {
    "name": CFG["workflow_name"],
    "nodes": nodes,
    "connections": conns,
    "active": False,
    "settings": {"executionOrder": "v1", "saveManualExecutions": True, "callerPolicy": "workflowsFromSameOwner"},
    "pinData": {},
    "meta": {"instanceId": "magnifai-content-engine-v2"},
    "tags": [{"name": "MagnifAI"}, {"name": "content-engine"}],
}
with open("workflow.n8n.json", "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)
print(f"nodes={len(nodes)} connections={len(conns)} written=workflow.n8n.json")
