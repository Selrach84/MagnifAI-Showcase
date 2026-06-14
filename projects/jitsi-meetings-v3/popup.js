/* Jitsi Meetings v3 — popup launcher + multistream (Go Live) manager.
   Pure functions exported on window.JM for tests. */
"use strict";
const DOMAIN = "jitsi.member.fsf.org";
const ADJ = ["Swift","Bright","Calm","Bold","Lucky","Cosmic","Golden","Brave","Clever","Quiet","Mighty","Sunny"];
const NOUN = ["Panda","Falcon","River","Comet","Maple","Tiger","Harbor","Orbit","Cedar","Vertex","Lotus","Summit"];

// Platform RTMP presets. Stable ingest URLs are prefilled; per-broadcast ones are blank
// (the platform hands you a Server URL + key per stream — paste it).
const PLATFORMS = {
  youtube:  { name:"YouTube",      url:"rtmp://a.rtmp.youtube.com/live2" },
  facebook: { name:"Facebook",     url:"rtmps://live-api-s.facebook.com:443/rtmp/" },
  twitch:   { name:"Twitch",       url:"rtmp://live.twitch.tv/app/" },
  tiktok:   { name:"TikTok",       url:"" },      // paste Server URL from TikTok LIVE Studio
  instagram:{ name:"Instagram",    url:"" },      // no official RTMP; via relay tool
  linkedin: { name:"LinkedIn",     url:"" },      // per-event URL from LinkedIn Live
  x:        { name:"X (Twitter)",  url:"" },      // Media Studio Producer URL
  kick:     { name:"Kick",         url:"" },
  trovo:    { name:"Trovo",        url:"rtmp://livepush.trovo.live/live/" },
  rumble:   { name:"Rumble",       url:"" },
  custom:   { name:"Custom RTMP",  url:"" }
};

const rnd = a => a[Math.floor(Math.random()*a.length)];
function randomRoom(){ return rnd(ADJ)+rnd(NOUN)+Math.floor(100+Math.random()*900); }

function normalizeRoom(input){
  let s = (input||"").trim();
  if(!s) return "";
  if(s.includes("://") || s.toLowerCase().includes("jit.si") || s.includes("/")){
    s = s.split("?")[0].split("#")[0].replace(/\/+$/,"");
    s = s.substring(s.lastIndexOf("/")+1);
  }
  return s.replace(/\s+/g,"").replace(/[^\w\-]/g,"");
}
function meetingUrl(room, opts){
  const p = new URLSearchParams({
    room, name: opts.name||"", am: opts.am?"1":"0", vm: opts.vm?"1":"0",
    subject: opts.subject||"", server: opts.server||"", large: opts.large===false?"0":"1"
  });
  return chrome.runtime.getURL("meeting.html") + "?" + p.toString();
}
function inviteLink(room, server){ return "https://"+(server||DOMAIN)+"/"+room; }

const store = {
  async get(k,d){ const o = await chrome.storage.local.get(k); return o[k]===undefined?d:o[k]; },
  async set(k,v){ return chrome.storage.local.set({[k]:v}); }
};
async function getSettings(){ return store.get("settings",{name:"",am:false,vm:false,server:"",large:true}); }
async function getLive(){ return store.get("live",{mode:"single",relayUrl:"",relayKey:"",destinations:[]}); }
async function setLive(v){ return store.set("live", v); }

async function addRecent(room,subject){
  let r = await store.get("recent",[]);
  r = r.filter(x=>x.room!==room);
  r.unshift({room,subject:subject||"",ts:Date.now()});
  await store.set("recent", r.slice(0,8));
}
async function openMeeting(room, opts){
  const r = normalizeRoom(room) || randomRoom();
  const s = await getSettings();
  const o = Object.assign({ name:s.name, am:s.am, vm:s.vm, server:s.server, large:s.large!==false }, opts||{});
  const url = meetingUrl(r,o);
  await addRecent(r, o.subject);
  chrome.tabs.create({ url });
  return url;
}

function fmtCalDate(d){ return d.toISOString().replace(/[-:]/g,"").split(".")[0]+"Z"; }
function calendarLink(title, room, when, server){
  const start = new Date(when), end = new Date(start.getTime()+3600000);
  const link = inviteLink(room, server);
  const p = new URLSearchParams({ action:"TEMPLATE", text:title||"Jitsi Meeting",
    dates: fmtCalDate(start)+"/"+fmtCalDate(end), details:"Join the video meeting: "+link, location:link });
  return "https://calendar.google.com/calendar/render?"+p.toString();
}

/* ---- multistream helpers (shared with meeting.js logic) ---- */
function joinRtmp(url,key){ if(!url) return ""; url=url.replace(/\/+$/,""); return key?url+"/"+key:url; }
function buildLiveTarget(cfg){
  cfg=cfg||{};
  if(cfg.mode==="relay") return joinRtmp(cfg.relayUrl, cfg.relayKey);
  const d=(cfg.destinations||[]).filter(x=>x.enabled && x.url);
  return d.length ? joinRtmp(d[0].url, d[0].key) : "";
}
function enabledDests(cfg){ return (cfg.destinations||[]).filter(d=>d.enabled && d.url); }
// ffmpeg single-input -> many-output fan-out (handles rtmp + rtmps). Run on your relay box.
function buildFfmpeg(cfg){
  const dests=enabledDests(cfg);
  const ingest = cfg.relayUrl ? joinRtmp(cfg.relayUrl,cfg.relayKey) : "rtmp://localhost/live/STREAM";
  if(!dests.length) return "# add at least one enabled destination first";
  const outs=dests.map(d=>"[f=flv:onfail=ignore]"+joinRtmp(d.url,d.key)).join("|");
  return "ffmpeg -i "+ingest+" -c copy -map 0 -f tee \""+outs+"\"";
}
// nginx-rtmp fan-out (RTMP only; for rtmps use the ffmpeg command or stunnel).
function buildNginx(cfg){
  const dests=enabledDests(cfg);
  const push=dests.map(d=>"      push "+joinRtmp(d.url,d.key)+";  # "+(d.name||d.platform)).join("\n");
  return "rtmp {\n  server {\n    listen 1935;\n    chunk_size 4096;\n    application live {\n      live on;\n"
    +(push||"      # add destinations")+"\n    }\n  }\n}\n"
    +"# nginx-rtmp output is RTMP-only. For rtmps (Facebook/Instagram) use the ffmpeg tee command.";
}

if (typeof window !== "undefined") {
  window.JM = { randomRoom, normalizeRoom, meetingUrl, inviteLink, openMeeting, calendarLink, fmtCalDate,
    PLATFORMS, buildLiveTarget, buildFfmpeg, buildNginx, joinRtmp, getLive, setLive };
}

/* ---------- UI ---------- */
function initUI(){
  const $ = id => document.getElementById(id);
  if(!$("view-home")) return;
  const views = ["home","join","sched","settings","live"];
  const show = v => views.forEach(x => $("view-"+x).classList.toggle("hidden", x!==v));

  let toastT;
  function toast(msg){ const t=$("toast"); t.textContent=msg; t.classList.remove("hidden");
    clearTimeout(toastT); toastT=setTimeout(()=>t.classList.add("hidden"),1800); }
  async function copy(text,msg){ try{ await navigator.clipboard.writeText(text); toast(msg||"Copied"); }catch(e){ toast("Copy failed"); } }

  document.querySelectorAll("[data-back]").forEach(b=>b.onclick=()=>show("home"));
  $("navSettings").onclick = async ()=>{ const s=await getSettings();
    $("setName").value=s.name; $("setAm").checked=s.am; $("setVm").checked=s.vm;
    $("setServer").value=s.server||""; $("setLarge").checked=s.large!==false; show("settings"); };

  $("btnNew").onclick = ()=>openMeeting(randomRoom(),{subject:"Instant meeting"});
  $("btnJoin").onclick = async ()=>{ const s=await getSettings();
    $("joinName").value=s.name; $("joinAm").checked=s.am; $("joinVm").checked=s.vm; show("join"); };
  $("btnSchedule").onclick = ()=>show("sched");
  $("btnShare").onclick = ()=>openMeeting(randomRoom(),{subject:"Screen share", share:"1"});
  $("btnLive").onclick = ()=>{ renderLive(); show("live"); };

  $("joinGo").onclick = ()=>{
    const room = $("joinRoom").value;
    if(!normalizeRoom(room)) return toast("Enter a meeting name");
    openMeeting(room,{ name:$("joinName").value, am:$("joinAm").checked, vm:$("joinVm").checked });
  };
  $("schSave").onclick = async ()=>{
    const title=$("schTitle").value.trim(), when=$("schWhen").value;
    if(!title||!when) return toast("Add a title and time");
    const room = normalizeRoom($("schRoom").value) || randomRoom();
    let list = await store.get("scheduled",[]);
    list.push({title,room,when}); list.sort((a,b)=>new Date(a.when)-new Date(b.when));
    await store.set("scheduled", list); toast("Scheduled"); show("home"); render();
  };
  $("setSave").onclick = async ()=>{
    const server=$("setServer").value.trim().replace(/^https?:\/\//,"").replace(/\/.*$/,"");
    await store.set("settings",{ name:$("setName").value.trim(),
      am:$("setAm").checked, vm:$("setVm").checked, server, large:$("setLarge").checked });
    toast("Saved"); show("home");
  };

  /* ----- Go Live manager ----- */
  let liveCfg = {mode:"single",relayUrl:"",relayKey:"",destinations:[]};
  function liveModeUI(){
    const relay = liveCfg.mode==="relay";
    $("liveRelayBox").classList.toggle("hidden", !relay);
    document.querySelectorAll('input[name="liveMode"]').forEach(r=>r.checked=(r.value===liveCfg.mode));
  }
  function renderDests(){
    const box=$("destList"); box.innerHTML="";
    if(!liveCfg.destinations.length){ box.appendChild(Object.assign(document.createElement("div"),{className:"empty",textContent:"No destinations. Add one below."})); }
    liveCfg.destinations.forEach((d,i)=>{
      const row=document.createElement("div"); row.className="dest";
      row.innerHTML=`<div class="dest-h">
          <label><input type="checkbox" class="d-en"> <b></b></label>
          <button class="d-rm" title="Remove">✕</button></div>
        <input class="d-url" type="text" placeholder="RTMP/RTMPS server URL">
        <input class="d-key" type="text" placeholder="Stream key">`;
      row.querySelector("b").textContent=d.name||d.platform;
      row.querySelector(".d-en").checked=d.enabled!==false;
      row.querySelector(".d-url").value=d.url||"";
      row.querySelector(".d-key").value=d.key||"";
      row.querySelector(".d-en").onchange=e=>liveCfg.destinations[i].enabled=e.target.checked;
      row.querySelector(".d-url").oninput=e=>liveCfg.destinations[i].url=e.target.value.trim();
      row.querySelector(".d-key").oninput=e=>liveCfg.destinations[i].key=e.target.value.trim();
      row.querySelector(".d-rm").onclick=()=>{ liveCfg.destinations.splice(i,1); renderDests(); };
      box.appendChild(row);
    });
  }
  async function renderLive(){
    liveCfg = await getLive();
    if(!liveCfg.destinations) liveCfg.destinations=[];
    $("liveRelayUrl").value=liveCfg.relayUrl||"";
    $("liveRelayKey").value=liveCfg.relayKey||"";
    const sel=$("destPreset"); sel.innerHTML="";
    Object.entries(PLATFORMS).forEach(([k,v])=>{ const o=document.createElement("option"); o.value=k; o.textContent=v.name; sel.appendChild(o); });
    liveModeUI(); renderDests();
  }
  document.querySelectorAll('input[name="liveMode"]').forEach(r=>r.onchange=()=>{ liveCfg.mode=r.value; liveModeUI(); });
  $("destAdd").onclick = ()=>{ const k=$("destPreset").value, p=PLATFORMS[k];
    liveCfg.destinations.push({platform:k,name:p.name,url:p.url,key:"",enabled:true}); renderDests(); };
  $("liveSave").onclick = async ()=>{
    liveCfg.relayUrl=$("liveRelayUrl").value.trim(); liveCfg.relayKey=$("liveRelayKey").value.trim();
    await setLive(liveCfg); toast("Live settings saved"); };
  $("liveFfmpeg").onclick = ()=>copy(buildFfmpeg(liveCfg),"ffmpeg fan-out copied");
  $("liveNginx").onclick  = ()=>copy(buildNginx(liveCfg),"nginx config copied");

  async function render(){
    const srv=(await getSettings()).server||"";
    const sl=$("schedList"), sched=await store.get("scheduled",[]);
    const now=Date.now(); const up = sched.filter(x=>new Date(x.when).getTime() > now-3600000);
    if(up.length!==sched.length){ await store.set("scheduled",up); }
    sl.innerHTML=""; $("schedEmpty").classList.toggle("hidden",up.length>0);
    up.forEach(m=>{
      const when=new Date(m.when).toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
      const li=document.createElement("li");
      li.innerHTML=`<div class="li-main"><div class="li-title"></div><div class="li-sub"></div></div>
        <button class="li-btn alt" data-a="cal">📅</button><button class="li-btn" data-a="start">Start</button>`;
      li.querySelector(".li-title").textContent=m.title;
      li.querySelector(".li-sub").textContent=when+" · "+m.room;
      li.querySelector('[data-a="start"]').onclick=()=>openMeeting(m.room,{subject:m.title});
      li.querySelector('[data-a="cal"]').onclick=()=>chrome.tabs.create({url:calendarLink(m.title,m.room,m.when,srv)});
      sl.appendChild(li);
    });
    const rl=$("recentList"), recent=await store.get("recent",[]);
    rl.innerHTML=""; $("recentEmpty").classList.toggle("hidden",recent.length>0);
    recent.forEach(m=>{
      const li=document.createElement("li");
      li.innerHTML=`<div class="li-main"><div class="li-title"></div><div class="li-sub"></div></div>
        <button class="li-btn alt" data-a="copy">Copy</button><button class="li-btn" data-a="join">Join</button>`;
      li.querySelector(".li-title").textContent=m.subject||m.room;
      li.querySelector(".li-sub").textContent=m.room;
      li.querySelector('[data-a="join"]').onclick=()=>openMeeting(m.room,{subject:m.subject});
      li.querySelector('[data-a="copy"]').onclick=()=>copy(inviteLink(m.room,srv),"Link copied");
      rl.appendChild(li);
    });
  }
  render();
}
if (typeof document !== "undefined") document.addEventListener("DOMContentLoaded", initUI);
