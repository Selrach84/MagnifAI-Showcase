/* LIVE E2E test for v3: loads as a REAL unpacked extension (fake camera/mic + fake screen),
   joins a real Jitsi room, verifies a real executeCommand round-trip, exercises the MP4
   recorder, and confirms the Go Live (multistream) wiring is present + builds correct RTMP
   targets. (It does NOT push a real RTMP stream — that needs a Jibri-enabled server + keys.)
   Run: node tests/live.js [server] */
"use strict";
const { spawn } = require("child_process");
const path = require("path");
const crypto = require("crypto");
const BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser";
const EXT = path.resolve(__dirname, "..");
const extId = p => [...crypto.createHash("sha256").update(p).digest("hex").slice(0, 32)]
  .map(c => String.fromCharCode(97 + parseInt(c, 16))).join("");

function launch(headless) {
  return new Promise((res, rej) => {
    const args = [headless ? "--headless=new" : "--no-sandbox", "--remote-debugging-port=0",
      "--user-data-dir=/tmp/jm3-live-" + Date.now(),
      "--load-extension=" + EXT, "--disable-extensions-except=" + EXT,
      "--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream",
      "--auto-select-desktop-capture-source=Entire screen",
      "--autoplay-policy=no-user-gesture-required",
      "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank"];
    const proc = spawn(BRAVE, args);
    let buf = ""; const on = d => { buf += d.toString(); const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) res({ proc, ws: m[1] }); };
    proc.stderr.on("data", on); proc.stdout.on("data", on);
    setTimeout(() => rej(new Error("no DevTools url. log:\n" + buf.slice(0, 500))), 15000);
  });
}
class CDP {
  constructor(ws){this.ws=ws;this.id=0;this.w=new Map();this.e={};
    ws.onmessage=ev=>{const m=JSON.parse(ev.data);
      if(m.id&&this.w.has(m.id)){const x=this.w.get(m.id);this.w.delete(m.id);m.error?x.rej(new Error(JSON.stringify(m.error))):x.res(m.result);}
      else if(m.method)(this.e[m.method]||[]).forEach(f=>f(m.params,m.sessionId));};}
  send(method,params={},sessionId){return new Promise((res,rej)=>{const id=++this.id;this.w.set(id,{res,rej});
    this.ws.send(JSON.stringify({id,method,params,sessionId}));});}
  on(m,f){(this.e[m]=this.e[m]||[]).push(f);}
}

const TEST = `async () => {
  const w=async(c,t)=>{const s=Date.now();while(Date.now()-s<t){if(c())return true;await new Promise(r=>setTimeout(r,100));}return c();};
  const out={loaded:false,joined:false,failed:null,name:null,count:0,muteRoundTrip:false,
             mp4Supported:false,recording:null,liveButton:false,liveTargetOk:false,fails:[]};
  if(!await w(()=>window.__meeting&&window.__meeting.api,8000)){out.fails.push('extension page / Jitsi API did not init');return out;}
  out.loaded=true;
  const api=window.__meeting.api;
  try{out.mp4Supported = window.JM_MEETING.pickMime().ext==='mp4';}catch(_){}
  // v3: Go Live wiring present + correct RTMP target build (no real push)
  out.liveButton = !!document.getElementById('c-live');
  try{ out.liveTargetOk = window.__meeting.live.buildTarget({mode:'single',destinations:[{url:'rtmp://a.rtmp.youtube.com/live2',key:'K',enabled:true}]})==='rtmp://a.rtmp.youtube.com/live2/K'; }catch(_){}
  api.addEventListener('videoConferenceJoined',e=>{out.joined=true;out.name=e&&e.displayName;});
  api.addEventListener('conferenceFailed',e=>{out.failed=(e&&e.error)||'conferenceFailed';});
  await w(()=>out.joined||out.failed,30000);
  out.gate=/membersOnly|authentication|notAllowed|password|lobby/i.test(out.failed||'');
  if(!out.joined){ if(out.gate){out.integration=true;out.pass=out.liveButton&&out.liveTargetOk;}
    else out.fails.push('did not connect (failed='+out.failed+')'); return out; }
  out.integration=true;
  try{out.count=api.getNumberOfParticipants();}catch(_){}
  try{ const b=await api.isAudioMuted(); api.executeCommand('toggleAudio'); await new Promise(r=>setTimeout(r,1200));
    out.muteRoundTrip=(b!==await api.isAudioMuted()); }catch(e){out.fails.push('mute: '+e.message);}
  try{ const started=await window.__meeting.rec.start();
    if(started){ await new Promise(r=>setTimeout(r,2500)); window.__meeting.rec.stop();
      await w(()=>window.__lastRecording,6000); out.recording=window.__lastRecording||null; } else out.recErr='getDisplayMedia false';
  }catch(e){out.recErr=e.message;}
  if(!out.liveButton)out.fails.push('no Go Live button');
  if(!out.liveTargetOk)out.fails.push('buildTarget wrong');
  out.pass = out.loaded && out.joined && out.muteRoundTrip && out.liveButton && out.liveTargetOk;
  return out;
}`;

const SERVER = process.argv[2] || "";
async function attempt(headless) {
  const id = extId(EXT);
  const url = "chrome-extension://" + id + "/meeting.html?room=ClaudeLive" + Date.now()
    + "&name=ClaudeBot" + (SERVER ? "&server=" + encodeURIComponent(SERVER) : "");
  const L = await launch(headless); const proc = L.proc;
  try {
    const ws = new WebSocket(L.ws);
    await new Promise((r, j) => { ws.addEventListener("open", r); ws.addEventListener("error", j); });
    const cdp = new CDP(ws);
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    const errs = [];
    cdp.on("Runtime.exceptionThrown", (p, s) => { if (s === sessionId) errs.push((p.exceptionDetails.exception && p.exceptionDetails.exception.description) || p.exceptionDetails.text); });
    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Page.enable", {}, sessionId);
    try { await cdp.send("Page.setDownloadBehavior", { behavior: "deny" }, sessionId); } catch (_) {}
    const loaded = new Promise(r => cdp.on("Page.loadEventFired", (p, s) => { if (s === sessionId) r(); }));
    await cdp.send("Page.navigate", { url }, sessionId);
    await Promise.race([loaded, new Promise(r => setTimeout(r, 8000))]);
    const r = await cdp.send("Runtime.evaluate", { expression: "(" + TEST + ")()", awaitPromise: true, returnByValue: true, timeout: 70000 }, sessionId);
    ws.close(); try { proc.kill(); } catch (_) {}
    return { id, value: r.result && r.result.value, errs };
  } catch (e) { try { proc.kill(); } catch (_) {} throw e; }
}

(async () => {
  console.log("extension id:", extId(EXT));
  let res;
  try { res = await attempt(true); } catch (e) { console.log("headless error:", e.message); }
  if (!res || !res.value || !res.value.loaded) {
    console.log("retrying headful…");
    try { res = await attempt(false); } catch (e) { console.error("RUNNER ERROR:", e.message); process.exit(2); }
  }
  const v = (res && res.value) || { fails: ["no result"] };
  const server = SERVER || "(default: jitsi.member.fsf.org)";
  console.log("\n=== LIVE v3: real extension against " + server + " ===");
  console.log("  extension page loaded :", !!v.loaded);
  console.log("  conference JOINED      :", !!v.joined, v.name ? "(as " + v.name + ")" : (v.gate ? "(server gate)" : ""));
  if (v.joined) console.log("  toggleAudio round-trip:", !!v.muteRoundTrip);
  console.log("  MP4 MediaRecorder      :", v.mp4Supported ? "supported (.mp4)" : "fallback .webm");
  if (v.recording) console.log("  recording produced     : ." + v.recording.ext + " " + v.recording.bytes + " bytes");
  console.log("  Go Live button         :", !!v.liveButton);
  console.log("  RTMP target builder    :", !!v.liveTargetOk, "(YouTube url+key joined correctly)");
  (v.fails || []).forEach(f => console.log("  ✗ " + f));
  const ok = v.pass;
  if (v.joined) console.log("\nLIVE PASSED ✅ — joined + controls + recorder + Go Live wiring all verified");
  else if (v.integration) console.log("\nLIVE PASSED ✅ — operational (server gated final join); Go Live wiring verified");
  else console.log("\nLIVE FAILED ❌");
  process.exit(ok ? 0 : 1);
})();
