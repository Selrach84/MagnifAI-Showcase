/* Smoke test: load the REAL meeting.html (with the bundled external_api.js) in headless
   Brave and confirm the genuine Jitsi IFrame API loads, the control bar renders, and the
   page initialises without fatal JS errors. (No camera/real call — just integration wiring.)
   Run: node tests/smoke.js */
"use strict";
const { spawn } = require("child_process");
const path = require("path");
const BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser";
const fileUrl = (p, q) => "file://" + encodeURI(path.resolve(__dirname, p)) + (q ? "?" + q : "");

function launch() {
  return new Promise((res, rej) => {
    const proc = spawn(BRAVE, ["--headless=new","--remote-debugging-port=0",
      "--user-data-dir=/tmp/jm-smoke-"+Date.now(),"--no-first-run","--no-default-browser-check","--disable-gpu","about:blank"]);
    let buf=""; const on=d=>{buf+=d.toString();const m=buf.match(/DevTools listening on (ws:\/\/\S+)/);if(m)res({proc,ws:m[1]});};
    proc.stderr.on("data",on); proc.stdout.on("data",on);
    setTimeout(()=>rej(new Error("no DevTools url")),15000);
  });
}
class CDP{constructor(ws){this.ws=ws;this.id=0;this.w=new Map();this.e={};
  ws.onmessage=ev=>{const m=JSON.parse(ev.data);
    if(m.id&&this.w.has(m.id)){const x=this.w.get(m.id);this.w.delete(m.id);m.error?x.rej(new Error(JSON.stringify(m.error))):x.res(m.result);}
    else if(m.method)(this.e[m.method]||[]).forEach(f=>f(m.params,m.sessionId));};}
  send(method,params={},sessionId){return new Promise((res,rej)=>{const id=++this.id;this.w.set(id,{res,rej});
    this.ws.send(JSON.stringify({id,method,params,sessionId}));});}
  on(m,f){(this.e[m]=this.e[m]||[]).push(f);}}

(async()=>{
  let proc;
  try{
    const L=await launch(); proc=L.proc;
    const ws=new WebSocket(L.ws);
    await new Promise((r,j)=>{ws.addEventListener("open",r);ws.addEventListener("error",j);});
    const cdp=new CDP(ws);
    const {targetId}=await cdp.send("Target.createTarget",{url:"about:blank"});
    const {sessionId}=await cdp.send("Target.attachToTarget",{targetId,flatten:true});
    const errs=[];
    cdp.on("Runtime.exceptionThrown",(p,sid)=>{if(sid===sessionId)errs.push((p.exceptionDetails.exception&&p.exceptionDetails.exception.description)||p.exceptionDetails.text);});
    await cdp.send("Runtime.enable",{},sessionId);
    await cdp.send("Page.enable",{},sessionId);
    const loaded=new Promise(r=>cdp.on("Page.loadEventFired",(p,sid)=>{if(sid===sessionId)r();}));
    await cdp.send("Page.navigate",{url:fileUrl("../meeting.html","room=SmokeTest&name=Tester")},sessionId);
    await Promise.race([loaded,new Promise(r=>setTimeout(r,6000))]);
    const fn=`async()=>{const w=async(c,t=6000)=>{const s=Date.now();while(Date.now()-s<t){if(c())return true;await new Promise(r=>setTimeout(r,50));}return false;};
      const f=[];
      if(typeof JitsiMeetExternalAPI!=='function')f.push('JitsiMeetExternalAPI not defined (bundled external_api.js failed)');
      if(!await w(()=>document.getElementById('c-mic')))f.push('control bar did not render');
      if(!document.getElementById('bar'))f.push('no #bar');
      if(!await w(()=>window.__meeting&&window.__meeting.api))f.push('Jitsi API object not created');
      const bar=document.querySelectorAll('#bar .ctrl').length;
      return {pass:f.length===0,fails:f,buttons:bar,jitsi:typeof JitsiMeetExternalAPI};}`;
    const r=await cdp.send("Runtime.evaluate",{expression:"("+fn+")()",awaitPromise:true,returnByValue:true},sessionId);
    const v=r.result.value||{pass:false,fails:["no result"]};
    console.log("=== smoke: real meeting.html + bundled external_api.js ===");
    console.log(v.pass?"PASS":"FAIL");
    (v.fails||[]).forEach(x=>console.log("  ✗ "+x));
    console.log("  control buttons rendered: "+v.buttons+" | JitsiMeetExternalAPI: "+v.jitsi);
    // ignore benign in-iframe network/getUserMedia errors; only fail on top-frame fatal
    const fatal=errs.filter(e=>/is not defined|TypeError.*meeting|Cannot read/i.test(e));
    if(fatal.length)fatal.forEach(e=>console.log("  ⚠ top-frame exception: "+e));
    ws.close(); try{proc.kill();}catch(_){}
    const ok=v.pass&&!fatal.length;
    console.log("\n"+(ok?"SMOKE PASSED ✅":"SMOKE FAILED ❌"));
    process.exit(ok?0:1);
  }catch(e){if(proc)try{proc.kill();}catch(_){};console.error("RUNNER ERROR:",e.message);process.exit(2);}
})();
