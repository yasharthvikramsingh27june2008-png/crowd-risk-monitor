const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'APP_SOURCE_readable.html'), 'utf8');
const scriptTag = html.lastIndexOf('<script>');
const scriptEnd = html.lastIndexOf('</script>');
assert.ok(scriptTag >= 0 && scriptEnd > scriptTag, 'readable HTML contains its inline application script');
const appScript = html.slice(scriptTag + '<script>'.length, scriptEnd).replace(/\ninit\(\);\s*$/, '\n');

function makeContext(extra = {}) {
  const sandbox = {
    console,
    performance: { now: () => 1000 },
    document: {},
    window: {},
    Image: class { set src(value) { this._src = value; } },
    requestAnimationFrame() {},
    setTimeout() { return 1; },
    clearTimeout() {},
    ...extra,
  };
  vm.createContext(sandbox);
  return sandbox;
}

function makeExecutorContext(){
  const state = {
    closed: [],
    sent: [],
    logs: [],
    gates: [{i:0,open:true},{i:1,open:true}],
  };
  const sandbox = {
    Guide: { plan: { gates:[{i:0},{i:1}], units:['U1','U2'], closedByPlan:[] } },
    Feed: {
      gates: state.gates,
      setGate(i, open){ this.gates[i].open = open; if (!open) state.closed.push(i); return true; },
    },
    Response: {
      pendingUnits(){ return [{id:'U1'},{id:'U2'}]; },
      commit(id){ state.sent.push(id); return true; },
    },
    UI: { meta:{gatesChanged:0,dispatched:0}, autoRan:false },
    Risk: { disp:false },
    sirenStop(){},
    logOperator(text){ state.logs.push(text); },
    beepRaw(){}, renderGateStates(){}, renderDispatch(){},
    __state:state,
  };
  vm.createContext(sandbox);
  const start = appScript.indexOf('function executePlan(auto, quiet=false, parts=null){');
  const endMarker = '\n}\n\n/* ---------- guidance rendering';
  const end = appScript.indexOf(endMarker, start);
  assert.ok(start >= 0 && end > start, 'independent response executor exists');
  vm.runInContext(appScript.slice(start, end + 2), sandbox);
  return sandbox;
}

test('application JavaScript parses without running browser startup', () => {
  assert.doesNotThrow(() => new vm.Script(appScript));
});

test('density bands share exact boundaries across the risk helper', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const bands = vm.runInContext(`[0,1.99,2,3.49,3.5,4.99,5,6.49,6.5,8].map(v => Risk.band(v))`, ctx);
  assert.deepEqual(Array.from(bands), [
    'low','low','busy','busy','elev','elev','high','high','crit','crit',
  ]);
});

test('manual readings bypass AUTO hysteresis and retain the model-agent count', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const result = vm.runInContext(`(()=>{
    APP.event={id:'manual-test',footprint:[620,520]};
    APP.arch=ARCHETYPES.converge_gap();
    Feed.loadGates(APP.arch); Feed.reset();
    Feed.addAgent(null, APP.arch, Feed.gates[0]);
    const before=Feed.agents.length;
    UI.densityMode='manual';
    Feed.manualDensity=7.2;
    Feed.computeDensity();
    Feed.zoneVals=Feed.zoneBoard();
    const immediate=Feed.agents.length;
    for(let i=0;i<100 && !Risk.active;i++){
      Feed.simTime += 0.5; Feed.zoneVals=Feed.zoneBoard();
      Risk.update(Feed.zoneVals,APP.arch.zones.map(z=>z.n));
    }
    return {before,immediate,after:Feed.agents.length,reading:Feed.pdMax,zones:Feed.zoneVals,band:Risk.band(Feed.pdMax),alarm:Risk.active};
  })()`, ctx);
  assert.equal(result.before, 1);
  assert.equal(result.immediate, result.before);
  assert.equal(result.after, result.before);
  assert.equal(result.reading, 7.2);
  assert.equal(result.band, 'crit');
  assert.equal(result.alarm, true, 'manual red test readings can latch the alarm once simulated confirmation time passes');
  assert.equal(result.zones.length, 5);
  assert.ok(Array.from(result.zones).every(value => value === 7.2));
  assert.equal(vm.runInContext('CrowdRiskLogic.zoneReading(4.2, 7.2, true)', ctx), 4.2);
});

test('natural AUTO governor eases arrivals below the alarm line and is independent of MANUAL input', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const out = vm.runInContext(`[
    CrowdRiskLogic.naturalHeadroom(3.5,false),
    CrowdRiskLogic.naturalHeadroom(4.1,false),
    CrowdRiskLogic.naturalHeadroom(4.7,false),
    CrowdRiskLogic.naturalHeadroom(8,true),
    NATURAL_CEIL < THRESHOLD,
  ]`, ctx);
  assert.equal(out[0], 1);
  assert.ok(Math.abs(out[1] - 0.5) < 1e-12);
  assert.deepEqual(Array.from(out.slice(2)), [0, 1, true]);
});

test('gate closure stops admissions and a non-emergency cannot close every gate', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const result = vm.runInContext(`(()=>{
    APP.event={id:'gates-test',footprint:[620,520]};
    APP.arch=ARCHETYPES.converge_gap();
    Feed.loadGates(APP.arch); Feed.reset();
    Guide.state='clear';
    const first=Feed.setGate(0,false);
    const lastRejected=!Feed.setGate(1,false);
    Guide.state='action';
    const lastAccepted=Feed.setGate(1,false);
    Feed.step(1,APP.arch,{spawnRate:8});
    return {first,lastRejected,lastAccepted,fed:Feed.fed,agents:Feed.agents.length,open:Feed.openGates()};
  })()`, ctx);
  assert.equal(result.first, true);
  assert.equal(result.lastRejected, true);
  assert.equal(result.lastAccepted, true);
  assert.equal(result.open, 0);
  assert.equal(result.fed, 0);
  assert.equal(result.agents, 0);
});

test('gate and dispatch AUTO modes are independent in the actual plan executor', () => {
  const gatesOnly = makeExecutorContext();
  const gateResult = vm.runInContext('executePlan(true,false,{gates:true,dispatch:false})', gatesOnly);
  assert.equal(gateResult.gates, 2);
  assert.equal(gateResult.units, 0);
  assert.deepEqual(Array.from(gatesOnly.__state.closed), [0,1]);
  assert.equal(gatesOnly.__state.sent.length, 0);

  const dispatchOnly = makeExecutorContext();
  const dispatchResult = vm.runInContext('executePlan(true,false,{gates:false,dispatch:true})', dispatchOnly);
  assert.equal(dispatchResult.gates, 0);
  assert.equal(dispatchResult.units, 2);
  assert.deepEqual(Array.from(dispatchOnly.__state.closed), []);
  assert.deepEqual(Array.from(dispatchOnly.__state.sent), ['U1','U2']);

  const neither = makeExecutorContext();
  const manualResult = vm.runInContext('executePlan(false,false,{gates:false,dispatch:false})', neither);
  assert.equal(manualResult.gates, 0);
  assert.equal(manualResult.units, 0);
});

test('flow-rate helper reports observed counts per simulated minute and handles zero time', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const values = vm.runInContext(`[CrowdRiskLogic.ratePerMinute(5,10),CrowdRiskLogic.ratePerMinute(5,0)]`, ctx);
  assert.deepEqual(Array.from(values), [30,0]);
});

test('query results are built with textContent and keyboard navigation is present', () => {
  const start = appScript.indexOf('function renderSuggestions(q){');
  const end = appScript.indexOf('\n}\n\n/* The search box is optional:', start);
  assert.ok(start >= 0 && end > start);
  const renderer = appScript.slice(start, end + 2);
  assert.match(renderer, /li\.textContent\s*=\s*`No demo event or place matches/);
  assert.doesNotMatch(renderer, /innerHTML/);
  assert.match(appScript, /ev\.key === 'ArrowDown'/);
  assert.match(appScript, /ev\.key === 'ArrowUp'/);
  assert.match(appScript, /aria-activedescendant/);
  assert.match(appScript, /list\.replaceChildren\(\); \/\/ gate names and roles are venue-specific/);
  assert.match(appScript, /guidanceReset\(\);\n  APP\.ackVisible = false;/);
});

test('unvalidated forecast UI and runtime are absent', () => {
  assert.doesNotMatch(appScript, /function buildForecast\s*\(/);
  assert.doesNotMatch(appScript, /const Prediction\s*=/);
  assert.doesNotMatch(html, /id="fc"|UNVALIDATED/);
});

test('the cumulative eight-step Surge path crosses the alarm line and latches the alarm', () => {
  const ctx = makeContext();
  vm.runInContext(appScript, ctx, { timeout: 5000 });
  const result = vm.runInContext(`(()=>{
    APP.event={id:'surge-eight-test',footprint:[620,520]};
    APP.arch=ARCHETYPES.converge_gap();
    Feed.loadGates(APP.arch); Feed.reset(); Risk.reset();
    for(let i=0;i<SURGE_MAX;i++) Feed.surge();
    let max=0, crossedAlarmLine=false;
    for(let i=0;i<700;i++){
      for(let j=0;j<8;j++) Feed.step(0.5,APP.arch,{spawnRate:11});
      Feed.computeDensity(); Feed.zoneVals=Feed.zoneBoard();
      Risk.update(Feed.zoneVals,APP.arch.zones.map(z=>z.n));
      max=Math.max(max,Feed.pdMax);
      if(Feed.zoneVals.some(v=>v>=THRESHOLD)) crossedAlarmLine=true;
      if(Risk.active) break;
    }
    return {steps:Feed.surgeClicks,target:Feed.targetCrowd(),max,crossedAlarmLine,active:Risk.active,simTime:Feed.simTime};
  })()`, ctx);
  assert.equal(result.steps, 8);
  assert.equal(result.target, 2700);
  assert.ok(result.max >= 5.0, 'the full demo escalation reaches the 5.0 alarm line');
  assert.equal(result.crossedAlarmLine, true);
  assert.ok(result.simTime - 18000 >= 45, 'confirmation takes simulated time, not one sample');
  assert.equal(result.active, true);
});

test('switching an AUTO response mode during the active plan applies only that plan part', () => {
  function activePlan(mode){
    const ctx = makeContext();
    vm.runInContext(appScript, ctx, { timeout:5000 });
    return vm.runInContext(`(()=>{
      APP.event={id:'mode-test',footprint:[620,520]};
      APP.arch=ARCHETYPES.converge_gap();
      Feed.loadGates(APP.arch); Feed.reset();
      Response.load(APP.arch,25,81);
      Feed.zoneVals=new Array(APP.arch.zones.length).fill(5.2);
      Guide.plan=buildPlan(2); Guide.plan.autoActions={gates:0,units:0};
      Guide.state='action'; Guide.items=[];
      UI.gateMode=${JSON.stringify(mode==='gates'?'auto':'manual')};
      UI.dspMode=${JSON.stringify(mode==='dispatch'?'auto':'manual')};
      renderGuide=()=>{}; renderGateStates=()=>{}; renderDispatch=()=>{};
      logOperator=()=>{}; beepRaw=()=>{}; sirenStop=()=>{};
      Guide.push=function(kind,title,body){ this.testNotice={kind,title,body}; };
      applyAutomaticPlanPart(${JSON.stringify(mode==='gates'?{gates:true,dispatch:false}:{gates:false,dispatch:true})});
      return {closed:Feed.gates.filter(g=>!g.open).length,open:Feed.openGates(),sent:Response.dispatched(),\
        gateAuto:Guide.plan.autoActions.gates,unitAuto:Guide.plan.autoActions.units,\
        notice:Guide.testNotice.body};
    })()`, ctx);
  }
  const gates = activePlan('gates');
  assert.equal(gates.closed, 1);
  assert.equal(gates.sent, 0, 'AUTO gate control must not auto-dispatch units');
  assert.equal(gates.gateAuto, 1);
  assert.equal(gates.unitAuto, 0);
  assert.match(gates.notice, /1 gate\(s\) closed/);
  assert.match(gates.notice, /dispatch the named unit/);

  const dispatch = activePlan('dispatch');
  assert.equal(dispatch.closed, 0, 'AUTO dispatch must leave gate controls untouched');
  assert.equal(dispatch.sent, 1);
  assert.equal(dispatch.gateAuto, 0);
  assert.equal(dispatch.unitAuto, 1);
  assert.match(dispatch.notice, /1 unit\(s\) sent/);
  assert.match(dispatch.notice, /close the named gate/);
});
