/* Headless functional tests for Jitsi Meetings v3 (Brave over CDP, no deps).
   Run: node tests/run.js
   Covers v1/v2 (controls, breakout, large-mode, MP4 mime) + v3 multistream:
   in-call Go Live wiring (Jitsi stream commands) and the ffmpeg/nginx fan-out generators. */
"use strict";
const { spawn } = require("child_process");
const path = require("path");
const BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser";
const fileUrl = (name, query) => "file://" + encodeURI(path.join(__dirname, name)) + (query ? "?" + query : "");

function launch() {
  return new Promise((res, rej) => {
    const proc = spawn(BRAVE, ["--headless=new","--remote-debugging-port=0",
      "--user-data-dir=/tmp/jm3-test-" + Date.now(),
      "--no-first-run","--no-default-browser-check","--disable-gpu","about:blank"]);
    let buf = ""; const on = d => { buf += d.toString(); const m = buf.match(/DevTools listening on (ws:\/\/\S+)/); if (m) res({ proc, ws: m[1] }); };
    proc.stderr.on("data", on); proc.stdout.on("data", on);
    setTimeout(() => rej(new Error("no DevTools url. log:\n" + buf)), 15000);
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
async function runPage(cdp, url, fnStr) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  const exceptions = [];
  cdp.on("Runtime.exceptionThrown", (p, sid) => { if (sid === sessionId) exceptions.push((p.exceptionDetails.exception && p.exceptionDetails.exception.description) || p.exceptionDetails.text); });
  await cdp.send("Runtime.enable", {}, sessionId);
  await cdp.send("Page.enable", {}, sessionId);
  const loaded = new Promise(r => cdp.on("Page.loadEventFired", (p, sid) => { if (sid === sessionId) r(); }));
  await cdp.send("Page.navigate", { url }, sessionId);
  await Promise.race([loaded, new Promise(r => setTimeout(r, 5000))]);
  const r = await cdp.send("Runtime.evaluate", { expression: "(" + fnStr + ")()", awaitPromise: true, returnByValue: true }, sessionId);
  await cdp.send("Target.closeTarget", { targetId });
  return { value: r.result && r.result.value, exceptions };
}

const MEETING_TEST = `async () => {
  const wait=async(c,t=3000)=>{const s=Date.now();while(Date.now()-s<t){if(c())return true;await new Promise(r=>setTimeout(r,25));}return false;};
  const fails=[];
  if(!await wait(()=>window.__meeting&&window.__meeting.api)) return {pass:false,fails:['meeting did not initialise']};
  const api=window.__meeting.api;
  const last=()=>window.__calls.length?window.__calls[window.__calls.length-1]:null;
  const ln=()=>{const c=last();return c?c.name:null;};
  const clk=(id,cmd)=>{const b=document.getElementById('c-'+id);if(!b){fails.push('missing '+id);return;}b.click();if(ln()!==cmd)fails.push(id+' -> '+ln()+' (want '+cmd+')');};
  const co=api.opts.configOverwrite;
  if(co.channelLastN!==25)fails.push('large channelLastN');
  if(!co.p2p||co.p2p.enabled!==false)fails.push('large p2p');
  clk('mic','toggleAudio'); clk('cam','toggleVideo'); clk('share','toggleShareScreen');
  clk('people','toggleParticipantsPane'); clk('chat','toggleChat'); clk('view','toggleTileView'); clk('leave','hangup');
  // breakout
  document.getElementById('broName').value='Group A'; document.getElementById('broAdd').click();
  if(ln()!=='addBreakoutRoom'||last().args[0]!=='Group A')fails.push('addBreakoutRoom');
  document.getElementById('broAuto').click(); if(ln()!=='autoAssignToBreakoutRooms')fails.push('autoAssign');
  api.emit('breakoutRoomsUpdated',{rooms:{m:{id:'m',isMainRoom:true,participants:{}},r1:{id:'r1',name:'Group A',isMainRoom:false,participants:{}}}});
  if(document.querySelectorAll('#broList .bro-row').length!==2)fails.push('breakout rows');
  // recorder mime
  const mm=window.JM_MEETING.pickMime(); if(!mm||(mm.ext!=='mp4'&&mm.ext!=='webm'))fails.push('pickMime');
  // === v3: GO LIVE ===
  if(!document.getElementById('c-live'))fails.push('no live button');
  const tgt=window.__meeting.live.buildTarget({mode:'single',destinations:[{url:'rtmp://a.rtmp.youtube.com/live2',key:'TESTKEY',enabled:true}]});
  if(tgt!=='rtmp://a.rtmp.youtube.com/live2/TESTKEY')fails.push('buildTarget='+tgt);
  // start live -> reads chrome.storage mock (YouTube/TESTKEY) -> startRecording stream
  await window.__meeting.live.start();
  const c=last();
  if(!c||c.name!=='startRecording')fails.push('live start cmd='+(c&&c.name));
  else if(!c.args[0]||c.args[0].mode!=='stream')fails.push('live mode!=stream');
  else if(c.args[0].rtmpStreamKey!=='rtmp://a.rtmp.youtube.com/live2/TESTKEY')fails.push('rtmpStreamKey='+c.args[0].rtmpStreamKey);
  window.__meeting.live.stop();
  if(ln()!=='stopRecording'||last().args[0]!=='stream')fails.push('live stop bad ('+ln()+')');
  // streaming status event -> LIVE badge + button
  api.emit('recordingStatusChanged',{mode:'stream',on:true});
  if(!document.getElementById('c-live').classList.contains('warn'))fails.push('live btn not active on stream');
  if(!document.getElementById('liveBadge').classList.contains('show'))fails.push('LIVE badge not shown');
  // events -> UI
  api.emit('audioMuteStatusChanged',{muted:true});
  if(document.querySelector('#c-mic .g').textContent!=='🔇')fails.push('mic glyph');
  api._n=4; api.emit('videoConferenceJoined',{id:'me'});
  if(document.getElementById('pcount').textContent!=='4')fails.push('pcount');
  return {pass:fails.length===0, fails, totalCalls:window.__calls.length};
}`;

const POPUP_TEST = `async () => {
  const wait=async(c,t=3000)=>{const s=Date.now();while(Date.now()-s<t){if(c())return true;await new Promise(r=>setTimeout(r,25));}return false;};
  const fails=[];
  if(!await wait(()=>window.JM)) return {pass:false,fails:['window.JM not exposed']};
  const JM=window.JM;
  if(JM.normalizeRoom('Team Sync')!=='TeamSync')fails.push('normalize');
  const url=await JM.openMeeting('Team Sync',{name:'Bob',am:true});
  if(new URL(window.__tabs[0].url).searchParams.get('large')!=='1')fails.push('large param');
  // === v3: multistream ===
  if(!JM.PLATFORMS||JM.PLATFORMS.youtube.url!=='rtmp://a.rtmp.youtube.com/live2')fails.push('YouTube preset');
  if(JM.PLATFORMS.facebook.url.indexOf('rtmps://')!==0)fails.push('FB rtmps preset');
  if(JM.buildLiveTarget({mode:'single',destinations:[{url:'rtmp://a.rtmp.youtube.com/live2',key:'k',enabled:true}]})!=='rtmp://a.rtmp.youtube.com/live2/k')fails.push('buildLiveTarget single');
  if(JM.buildLiveTarget({mode:'relay',relayUrl:'rtmp://r/live',relayKey:'rk'})!=='rtmp://r/live/rk')fails.push('buildLiveTarget relay');
  const cfg={mode:'relay',relayUrl:'rtmp://localhost/live',relayKey:'S',destinations:[
    {name:'YouTube',url:'rtmp://a.rtmp.youtube.com/live2',key:'YT',enabled:true},
    {name:'Facebook',url:'rtmps://live-api-s.facebook.com:443/rtmp/',key:'FB',enabled:true},
    {name:'Off',url:'rtmp://x/y',key:'Z',enabled:false}]};
  const ff=JM.buildFfmpeg(cfg);
  if(ff.indexOf('-f tee')<0)fails.push('ffmpeg tee');
  if(ff.indexOf('rtmp://a.rtmp.youtube.com/live2/YT')<0)fails.push('ffmpeg YT out');
  if(ff.indexOf('rtmps://live-api-s.facebook.com:443/rtmp/FB')<0)fails.push('ffmpeg FB out');
  if(ff.indexOf('/Z')>=0)fails.push('ffmpeg included disabled dest');
  const ng=JM.buildNginx(cfg);
  if((ng.match(/push /g)||[]).length!==2)fails.push('nginx push count');
  // setLive/getLive roundtrip via mock storage
  await JM.setLive({mode:'relay',relayUrl:'rtmp://r/live',relayKey:'rk',destinations:[]});
  if((await JM.getLive()).mode!=='relay')fails.push('live storage roundtrip');
  return {pass:fails.length===0, fails};
}`;

(async () => {
  let proc;
  try {
    const launched = await launch(); proc = launched.proc;
    const ws = new WebSocket(launched.ws);
    await new Promise((r, j) => { ws.addEventListener("open", r); ws.addEventListener("error", j); });
    const cdp = new CDP(ws);
    const meeting = await runPage(cdp, fileUrl("mock-meeting.html", "room=Team%20Sync&name=Bob&am=1&subject=Standup"), MEETING_TEST);
    const popup   = await runPage(cdp, fileUrl("mock-popup.html"), POPUP_TEST);
    const report = (name, r) => {
      const v = r.value || { pass: false, fails: ["no result"] };
      console.log("\n=== " + name + " ==="); console.log(v.pass ? "PASS" : "FAIL");
      (v.fails || []).forEach(f => console.log("  ✗ " + f));
      if (r.exceptions.length) r.exceptions.forEach(e => console.log("  ⚠ exception: " + e));
      if (v.totalCalls != null) console.log("  (executeCommand calls captured: " + v.totalCalls + ")");
      return v.pass && !r.exceptions.length;
    };
    const ok1 = report("meeting page (controls + breakout + MP4 + GO LIVE)", meeting);
    const ok2 = report("popup launcher (logic + multistream generators)", popup);
    ws.close(); try { proc.kill(); } catch (_) {}
    console.log("\n" + (ok1 && ok2 ? "ALL TESTS PASSED ✅" : "TESTS FAILED ❌"));
    process.exit(ok1 && ok2 ? 0 : 1);
  } catch (e) {
    if (proc) try { proc.kill(); } catch (_) {}
    console.error("RUNNER ERROR:", e.message); process.exit(2);
  }
})();
