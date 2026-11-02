const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let strategy;
vm.runInNewContext(fs.readFileSync('custom_components/frizzlife_readonly/frontend/dashboard.js','utf8'), {
  HTMLElement: class {}, customElements:{get:()=>null,define:(name,value)=>{strategy=value;}}
});
(async () => {
  const hass={callWS:async ({type})=>type.includes('device_registry')?
    [{id:'monitor1',name:'Water monitor',identifiers:[['frizzlife_readonly','abc_123']]}]:
    [{device_id:'monitor1',unique_id:'abc_123_water_today',entity_id:'sensor.renamed_usage'},
     {device_id:'monitor1',unique_id:'abc_123_valve_position',entity_id:'sensor.valve_position'},
     {device_id:'monitor1',unique_id:'abc_123_fault_hardware',entity_id:'binary_sensor.hardware_fault'},
     {device_id:'monitor1',unique_id:'abc_123_mode_group',entity_id:'sensor.protection_mode'},
     {device_id:'monitor1',unique_id:'abc_123_pressure',entity_id:'sensor.hidden',hidden_by:'user'},
     {device_id:'monitor1',unique_id:'abc_123_switch',entity_id:'switch.valve'}]};
  const config=await strategy.generate({},hass);
  assert.equal(config.views.length,4);
  const data=JSON.stringify(config);
  assert(data.includes('sensor.renamed_usage'));
  assert(data.includes('binary_sensor.hardware_fault'));
  assert(data.includes('sensor.protection_mode'));
  assert(data.includes('Unverified event and test readings'));
  assert(!data.includes('sensor.hidden'));
  assert(!data.includes('switch.valve'));
  assert(!data.includes('call-service'));
  assert(data.includes('"stat_types":["change"]'));
  console.log('PASS: renamed registry entities, hidden/control exclusion and daily counter graph.');
})();
