/* Jitsi Meetings v3 — Zoom-style control bar over the Jitsi IFrame API.
   v3 adds: GO LIVE multistream (Jibri RTMP) to YouTube/Facebook/Twitch/TikTok/Instagram/…
   (v2: MP4 recording, breakout rooms, large-meeting mode). */
"use strict";
(function(){
const P = new URLSearchParams(location.search);
const params = {
  room:   (P.get("room")||"Demo").replace(/[^\w\-]/g,"") || "Demo",
  name:    P.get("name")||"",
  am:      P.get("am")==="1",
  vm:      P.get("vm")==="1",
  subject: P.get("subject")||"",
  share:   P.get("share")==="1",
  server:  (P.get("server")||"").replace(/^https?:\/\//,"").replace(/\/.*$/,""),
  large:   P.get("large")!=="0"
};
const DOMAIN = params.server || "jitsi.member.fsf.org";

let api=null, myId=null, t0=0, timerInt=null, joined=false, wdT=null;
let mediaRec=null, recChunks=[], recStream=null, recMic=null, recMime="", recExt="";
let breakoutRooms={}, liveOn=false;

const el=(t,a,h)=>{ const e=document.createElement(t);
  if(a) for(const k in a) e.setAttribute(k,a[k]); if(h!=null) e.innerHTML=h; return e; };
const $=id=>document.getElementById(id);
const inviteLink=()=>"https://"+DOMAIN+"/"+params.room;
const copy=async t=>{ try{ await navigator.clipboard.writeText(t); }catch(_){} };
let toastT;
function toast(m){ let t=$("toast"); if(!t){ t=el("div",{id:"toast"}); document.body.appendChild(t); }
  t.textContent=m; t.classList.add("show"); clearTimeout(toastT);
  toastT=setTimeout(()=>t.classList.remove("show"),2800); }

/* ---- live (multistream) config helpers ---- */
function getLive(){
  if(typeof chrome!=="undefined" && chrome.storage && chrome.storage.local)
    return chrome.storage.local.get("live").then(o=>o.live||{});
  return Promise.resolve(window.__liveConfig||{});
}
// rtmp base + key -> full rtmp url
function joinRtmp(url,key){ if(!url) return ""; url=url.replace(/\/+$/,""); return key?url+"/"+key:url; }
function buildLiveTarget(cfg){
  cfg=cfg||{};
  if(cfg.mode==="relay") return joinRtmp(cfg.relayUrl, cfg.relayKey);
  const d=(cfg.destinations||[]).filter(x=>x.enabled && x.url);
  return d.length ? joinRtmp(d[0].url, d[0].key) : "";
}
function liveSummary(cfg){
  cfg=cfg||{};
  if(cfg.mode==="relay") return cfg.relayUrl ? "Relay → "+cfg.relayUrl+" (fans out to your platforms)" : "Relay not configured";
  const d=(cfg.destinations||[]).filter(x=>x.enabled && x.url);
  if(!d.length) return "No destination set — configure in the extension popup → Go Live";
  return "Streaming to "+(d[0].name||d[0].platform||"RTMP")+(d.length>1?(" (+"+(d.length-1)+" more via relay)"):"");
}

function buildUI(){
  const top=el("div",{id:"topbar"});
  top.innerHTML=`<div id="mtitle"></div><div id="timer">00:00</div>
    <span id="liveBadge" class="live-badge">● LIVE</span>
    <div class="spacer"></div>
    <div class="count"><span>👥</span><span id="pcount">1</span></div>
    <button class="mini" id="btnCopy">Copy invite</button>
    <button class="mini" id="btnFull">⛶ Fullscreen</button>`;
  document.body.appendChild(top);
  $("mtitle").textContent = params.subject || params.room;

  const bar=el("div",{id:"bar"});
  [["mic","🎤","Mute"],["cam","🎥","Stop Video"],["share","🖥️","Share"],
   ["people","👥","Participants"],["chat","💬","Chat"],["react","✋","Raise Hand"],
   ["view","▦","View"],["rooms","🧩","Rooms"],["record","⏺","Record"],
   ["live","📡","Go Live"],["more","⋯","More"],["leave","📞","Leave"]
  ].forEach(([id,g,t])=>{
    const b=el("button",{class:"ctrl"+(id==="leave"?" leave":""),id:"c-"+id});
    b.innerHTML=`<span class="g">${g}</span><span class="t">${t}</span>`;
    bar.appendChild(b);
  });
  document.body.appendChild(bar);

  const more=el("div",{id:"more"});
  more.innerHTML=`<button data-m="bg">🌫️ Virtual background</button>
    <button data-m="muteall">🔇 Mute everyone</button>
    <button data-m="filmstrip">🎞️ Toggle filmstrip</button>
    <button data-m="invite">🔗 Copy meeting link</button>`;
  document.body.appendChild(more);

  const bro=el("div",{id:"breakout"});
  bro.innerHTML=`<div class="bro-h">Breakout rooms</div>
    <div id="broList" class="bro-list"></div>
    <div class="bro-add"><input id="broName" type="text" placeholder="Room name (optional)">
      <button id="broAdd" class="bro-btn">Add</button></div>
    <button id="broAuto" class="bro-btn alt full">Auto-assign everyone</button>`;
  document.body.appendChild(bro);

  const live=el("div",{id:"live"});
  live.innerHTML=`<div class="bro-h">📡 Go Live</div>
    <div id="liveTarget" class="live-target">…</div>
    <div id="liveStatus" class="live-status">Offline</div>
    <div class="row2">
      <button id="liveStart" class="bro-btn">Start live</button>
      <button id="liveStop" class="bro-btn alt">Stop live</button>
    </div>
    <div class="live-note">Streaming runs server-side (Jitsi Jibri). Needs a server with
      streaming enabled (JaaS or self-host). Configure destinations in the popup → Go Live.</div>`;
  document.body.appendChild(live);

  const bye=el("div",{id:"bye"});
  bye.innerHTML=`<h1>You left the meeting</h1>
    <div class="b"><button id="rejoin">Rejoin</button><button id="close">Close tab</button></div>`;
  document.body.appendChild(bye);
}

const setActive=(id,on,warn)=>{ const b=$("c-"+id); if(b) b.classList.toggle(warn?"warn":"active",!!on); };
const setGlyph=(id,g)=>{ const e=document.querySelector("#c-"+id+" .g"); if(e) e.textContent=g; };
const setLabel=(id,t)=>{ const e=document.querySelector("#c-"+id+" .t"); if(e) e.textContent=t; };

function startTimer(){ t0=Date.now(); clearInterval(timerInt);
  timerInt=setInterval(()=>{ const s=Math.floor((Date.now()-t0)/1000);
    const m=String(Math.floor(s/60)).padStart(2,"0"), ss=String(s%60).padStart(2,"0");
    if($("timer")) $("timer").textContent=m+":"+ss; },1000); }
function updCount(){ try{ const n=api.getNumberOfParticipants(); if($("pcount")) $("pcount").textContent=n; }catch(_){} }

/* ---------- MP4 recording ---------- */
function pickMime(){
  const c=[["video/mp4;codecs=avc1.42E01E,mp4a.40.2","mp4"],["video/mp4;codecs=avc1,mp4a","mp4"],
           ["video/mp4;codecs=avc1","mp4"],["video/mp4","mp4"],
           ["video/webm;codecs=vp9,opus","webm"],["video/webm;codecs=vp8,opus","webm"],["video/webm","webm"]];
  for(const [m,x] of c){ if(window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) return {mime:m,ext:x}; }
  return {mime:"",ext:"webm"};
}
async function startRec(){
  if(mediaRec && mediaRec.state==="recording") return false;
  try{ recStream=await navigator.mediaDevices.getDisplayMedia({video:{frameRate:30},audio:true}); }
  catch(e){ toast("Recording cancelled"); return false; }
  let audioTrack=null;
  try{
    const AC=window.AudioContext||window.webkitAudioContext, ac=new AC(), dest=ac.createMediaStreamDestination();
    if(recStream.getAudioTracks().length) ac.createMediaStreamSource(new MediaStream([recStream.getAudioTracks()[0]])).connect(dest);
    try{ recMic=await navigator.mediaDevices.getUserMedia({audio:true}); ac.createMediaStreamSource(recMic).connect(dest); }catch(_){}
    audioTrack=dest.stream.getAudioTracks()[0];
  }catch(_){ audioTrack=recStream.getAudioTracks()[0]||null; }
  const tracks=[recStream.getVideoTracks()[0]]; if(audioTrack) tracks.push(audioTrack);
  const out=new MediaStream(tracks);
  const m=pickMime(); recMime=m.mime; recExt=m.ext;
  try{ mediaRec = recMime ? new MediaRecorder(out,{mimeType:recMime}) : new MediaRecorder(out); }
  catch(_){ mediaRec=new MediaRecorder(out); recMime=mediaRec.mimeType||""; recExt=/mp4/.test(recMime)?"mp4":"webm"; }
  recChunks=[];
  mediaRec.ondataavailable=e=>{ if(e.data && e.data.size) recChunks.push(e.data); };
  mediaRec.onstop=saveRec;
  recStream.getVideoTracks()[0].addEventListener("ended",()=>{ if(mediaRec && mediaRec.state!=="inactive") stopRec(); });
  mediaRec.start(1000);
  setActive("record",true,true); setLabel("record","Stop"); setGlyph("record","⏹");
  toast(recExt==="mp4" ? "Recording… (MP4)" : "Recording… MP4 unsupported, saving WebM");
  return true;
}
function stopRec(){
  try{ if(mediaRec && mediaRec.state!=="inactive") mediaRec.stop(); }catch(_){}
  if(recStream) recStream.getTracks().forEach(t=>t.stop());
  if(recMic) recMic.getTracks().forEach(t=>t.stop());
  setActive("record",false,true); setLabel("record","Record"); setGlyph("record","⏺");
}
function saveRec(){
  const type=recMime || (recExt==="mp4"?"video/mp4":"video/webm");
  const blob=new Blob(recChunks,{type});
  window.__lastRecording={ext:recExt,mime:type,bytes:blob.size};
  if(!blob.size){ toast("Nothing recorded"); return; }
  const url=URL.createObjectURL(blob);
  const name="meeting-"+params.room+"-"+new Date().toISOString().replace(/[:.]/g,"-")+"."+recExt;
  const a=el("a"); a.href=url; a.download=name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),10000);
  toast("Saved "+name);
}
function toggleRecord(){ (mediaRec && mediaRec.state==="recording") ? stopRec() : startRec(); }

/* ---------- live multistream ---------- */
async function renderLive(){
  const cfg=await getLive();
  if($("liveTarget")) $("liveTarget").textContent=liveSummary(cfg);
}
async function startLive(){
  const cfg=await getLive();
  const target=buildLiveTarget(cfg);
  if(!target){ toast("No live destination — open the popup → Go Live to add one"); if($("liveStatus")) $("liveStatus").textContent="No destination configured"; return false; }
  try{ api.executeCommand("startRecording",{mode:"stream", rtmpStreamKey:target}); }
  catch(e){ toast("Live start failed: "+e.message); return false; }
  liveOn=true; setActive("live",true,true); setGlyph("live","🔴"); setLabel("live","Live");
  if($("liveStatus")) $("liveStatus").textContent="Connecting… (server is starting the RTMP stream)";
  toast("Going live…");
  return true;
}
function stopLive(){
  try{ api.executeCommand("stopRecording","stream"); }catch(_){}
  liveOn=false; setActive("live",false,true); setGlyph("live","📡"); setLabel("live","Go Live");
  if($("liveStatus")) $("liveStatus").textContent="Offline";
  if($("liveBadge")) $("liveBadge").classList.remove("show");
}
function toggleLive(){ liveOn ? stopLive() : startLive(); }

function toggleFull(){
  if(!document.fullscreenElement) document.documentElement.requestFullscreen && document.documentElement.requestFullscreen();
  else document.exitFullscreen && document.exitFullscreen();
}

function renderBreakout(){
  const list=$("broList"); if(!list) return; list.innerHTML="";
  const rooms=Object.values(breakoutRooms||{});
  if(!rooms.length){ list.appendChild(el("div",{class:"bro-empty"},"No breakout rooms yet.")); return; }
  rooms.forEach(r=>{
    const n = r.participants ? Object.keys(r.participants).length : (r.participantsCount||0);
    const row=el("div",{class:"bro-row"});
    row.appendChild(el("span",{class:"bro-name"}, (r.isMainRoom?"Main room":(r.name||"Room"))+" ("+n+")"));
    if(!r.isMainRoom){ const cl=el("button",{class:"bro-btn alt"},"Close");
      cl.onclick=()=>api.executeCommand("closeBreakoutRoom",r.id); row.appendChild(cl); }
    const jn=el("button",{class:"bro-btn"},"Join");
    jn.onclick=()=>api.executeCommand("joinBreakoutRoom",r.id); row.appendChild(jn);
    list.appendChild(row);
  });
}

function wire(){
  const cmd=c=>()=>api.executeCommand(c);
  $("c-mic").onclick    = cmd("toggleAudio");
  $("c-cam").onclick    = cmd("toggleVideo");
  $("c-share").onclick  = cmd("toggleShareScreen");
  $("c-people").onclick = cmd("toggleParticipantsPane");
  $("c-chat").onclick   = cmd("toggleChat");
  $("c-react").onclick  = cmd("toggleRaiseHand");
  $("c-view").onclick   = cmd("toggleTileView");
  $("c-rooms").onclick  = ()=>$("breakout").classList.toggle("show");
  $("c-record").onclick = toggleRecord;
  $("c-live").onclick   = ()=>{ const p=$("live"); p.classList.toggle("show"); if(p.classList.contains("show")) renderLive(); };
  $("c-more").onclick   = ()=>$("more").classList.toggle("show");
  $("c-leave").onclick  = ()=>api.executeCommand("hangup");

  $("btnCopy").onclick  = ()=>copy(inviteLink());
  $("btnFull").onclick  = toggleFull;

  document.querySelectorAll("#more button").forEach(b=>b.onclick=()=>{
    const m=b.getAttribute("data-m");
    if(m==="bg")            api.executeCommand("toggleVirtualBackgroundDialog");
    else if(m==="muteall")  api.executeCommand("muteEveryone");
    else if(m==="filmstrip")api.executeCommand("toggleFilmStrip");
    else if(m==="invite")   copy(inviteLink());
    $("more").classList.remove("show");
  });

  $("broAdd").onclick  = ()=>{ const n=$("broName").value.trim();
    api.executeCommand("addBreakoutRoom", n||undefined); $("broName").value=""; };
  $("broAuto").onclick = ()=>api.executeCommand("autoAssignToBreakoutRooms");

  $("liveStart").onclick = startLive;
  $("liveStop").onclick  = stopLive;

  $("rejoin").onclick = ()=>location.reload();
  $("close").onclick  = ()=>window.close();
}

function events(){
  api.addEventListener("videoConferenceJoined", e=>{
    joined=true; clearTimeout(wdT); myId=e&&e.id; startTimer(); updCount();
    if(params.subject) api.executeCommand("subject", params.subject);
    if(params.share)   api.executeCommand("toggleShareScreen");
  });
  api.addEventListener("participantJoined", updCount);
  api.addEventListener("participantLeft", updCount);
  api.addEventListener("audioMuteStatusChanged", e=>{
    setActive("mic",e.muted,true); setGlyph("mic",e.muted?"🔇":"🎤"); setLabel("mic",e.muted?"Unmute":"Mute"); });
  api.addEventListener("videoMuteStatusChanged", e=>{
    setActive("cam",e.muted,true); setGlyph("cam",e.muted?"🚫":"🎥"); setLabel("cam",e.muted?"Start Video":"Stop Video"); });
  api.addEventListener("screenSharingStatusChanged", e=>setActive("share",e.on));
  api.addEventListener("tileViewChanged", e=>setActive("view",e.enabled));
  api.addEventListener("raiseHandUpdated", e=>{ if(e && e.id===myId) setActive("react",!!e.handRaised); });
  api.addEventListener("breakoutRoomsUpdated", e=>{ breakoutRooms=(e&&e.rooms)||e||{}; renderBreakout(); });
  api.addEventListener("recordingStatusChanged", e=>{
    if(!e || e.mode!=="stream") return;
    liveOn=!!e.on; setActive("live",liveOn,true);
    setGlyph("live",liveOn?"🔴":"📡"); setLabel("live",liveOn?"Live":"Go Live");
    if($("liveStatus")) $("liveStatus").textContent=liveOn?"● LIVE — streaming":("Offline"+(e.error?(" ("+e.error+")"):""));
    if($("liveBadge")) $("liveBadge").classList.toggle("show",liveOn);
  });
  api.addEventListener("readyToClose", ()=>{ clearInterval(timerInt);
    try{ api.dispose(); }catch(_){} if($("bye")) $("bye").style.display="flex"; });
  api.addEventListener("conferenceFailed", e=>{
    const err=(e&&e.error)||"";
    if(/membersOnly|authentication|notAllowed|password/i.test(err))
      showFallback("This room needs a moderator or sign-in on “"+DOMAIN+"”.");
  });
}

function showFallback(msg){
  if(joined) return;
  const bye=$("bye"); if(!bye) return;
  const h=bye.querySelector("h1"); if(h) h.textContent="Can't connect in-app";
  if(!bye.querySelector(".gate-hint")){
    const p=document.createElement("p"); p.className="gate-hint";
    p.style.cssText="max-width:540px;text-align:center;color:#9aa0b4;line-height:1.5;margin:0 20px";
    p.textContent=(msg||"The meeting couldn't load.")+" Some servers also block embedding. "
      +"Open the room directly on the server, or pick a different Jitsi server in Settings.";
    bye.insertBefore(p, bye.querySelector(".b"));
  }
  const row=bye.querySelector(".b");
  if(row && !row.querySelector("#openServer")){
    const b=document.createElement("button"); b.id="openServer";
    b.textContent="Open on "+DOMAIN; b.style.cssText="background:#23b26d;color:#fff;border-color:#23b26d";
    b.onclick=()=>window.open("https://"+DOMAIN+"/"+params.room,"_blank");
    row.insertBefore(b,row.firstChild);
  }
  bye.style.display="flex";
}

function largeConfig(){
  return params.large ? {
    channelLastN: 25, startVideoMuted: 25, startAudioMuted: 50,
    enableLayerSuspension: true, disableAudioLevels: true,
    p2p: { enabled: false }, constraints: { video: { height: { ideal: 180, max: 360 } } }
  } : {};
}

function init(){
  buildUI();
  if(typeof JitsiMeetExternalAPI==="undefined"){ if($("mtitle")) $("mtitle").textContent="⚠️ Jitsi failed to load"; return; }
  api=new JitsiMeetExternalAPI(DOMAIN,{
    roomName: params.room, parentNode: $("stage"), width:"100%", height:"100%",
    userInfo: params.name ? {displayName:params.name} : undefined,
    configOverwrite: Object.assign({
      prejoinPageEnabled:false, prejoinConfig:{enabled:false},
      startWithAudioMuted:params.am, startWithVideoMuted:params.vm,
      disableDeepLinking:true, toolbarButtons:[], disableInviteFunctions:true,
      subject: params.subject || undefined
    }, largeConfig()),
    interfaceConfigOverwrite:{
      TOOLBAR_BUTTONS:[], SHOW_JITSI_WATERMARK:false, SHOW_WATERMARK_FOR_GUESTS:false,
      MOBILE_APP_PROMO:false, HIDE_INVITE_MORE_HEADER:true, DISABLE_JOIN_LEAVE_NOTIFICATIONS:true
    }
  });
  wire(); events();
  wdT=setTimeout(()=>{ if(!joined) showFallback("Couldn't connect to “"+DOMAIN+"”."); },15000);
  window.__meeting={api,params,
    rec:{start:startRec,stop:stopRec,toggle:toggleRecord,pickMime},
    live:{start:startLive,stop:stopLive,toggle:toggleLive,buildTarget:buildLiveTarget,getLive,summary:liveSummary}};
}

if(typeof document!=="undefined") document.addEventListener("DOMContentLoaded",init);
window.JM_MEETING={params, buildUI, init, pickMime, buildLiveTarget, liveSummary, get api(){return api;}};
})();
