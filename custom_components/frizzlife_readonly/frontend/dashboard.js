/* Registry-based native Lovelace dashboard. No service calls or valve controls. */
(() => {
  const domain = 'frizzlife_readonly';
  const labels = {pressure:'Water pressure',flow:'Live flow',water_today:'Water used today',
    reported_104:'DP104 raw reading',valve_position:'Valve position',protection:'Protection',
    leak_warning:'Leak warning',leak_alarm:'Leak alarm',faults:'Reported fault bitmap',
    pressure_raw:'Pressure raw reading',measurement_units:'Reported measurement units',last_poll:'Last successful local poll'};
  class FrizzlifeStrategy extends HTMLElement {
    static async generate(config, hass) {
      const [devices, entities] = await Promise.all([
        hass.callWS({type:'config/device_registry/list'}),
        hass.callWS({type:'config/entity_registry/list'})]);
      const views = [];
      for (const device of devices) {
        const identity = device.identifiers?.find(id => id[0] === domain);
        if (!identity || device.disabled_by) continue;
        const prefix = identity[1] + '_';
        const map = Object.fromEntries(entities.filter(e => e.device_id === device.id &&
          !e.disabled_by && !e.hidden_by && /^(sensor|binary_sensor)\./.test(e.entity_id) &&
          e.unique_id?.startsWith(prefix)).map(e => [e.unique_id.slice(prefix.length),e.entity_id]));
        const rows = keys => keys.filter(k=>map[k]).map(k=>({entity:map[k],name:labels[k]}));
        const group = (title,keys) => ({type:'entities',title,show_header_toggle:false,entities:rows(keys)});
        const history = (title,keys) => ({type:'history-graph',title,hours_to_show:24,entities:rows(keys)});
        const name = device.name_by_user || device.name || 'Water monitor';
        const overview = [
          {type:'markdown',content:`# ${name}\nLocal water readings · LP365-P`},
          group('Live readings',['pressure','flow','water_today']),
          group('Monitor status',['valve_position','protection','leak_warning','leak_alarm']),
          history('Pressure · last 24 hours',['pressure']),history('Flow · last 24 hours',['flow'])];
        const usage = [{type:'markdown',content:'## Water usage\nThe device reports a daily counter, which resets at midnight. Home Assistant records its increases across resets. Select **Water used today** as the water source in Energy. History starts when Recorder first sees this entity; previous app history is not imported.'},
          group('Reported consumption',['water_today'])];
        if (map.water_today) usage.push({type:'statistics-graph',title:'Daily water use · 14 days',
          chart_type:'bar',period:'day',days_to_show:14,stat_types:['change'],entities:[map.water_today]});
        const diagnostic = [group('Reported device data',['last_poll','pressure_raw','measurement_units','faults','reported_104']),
          {type:'markdown',content:'This integration reads local status every 30 seconds. It provides no valve, reset, pairing or protection commands. Missing readings are unavailable. The raw fault bitmap is zero when the monitor reports no fault bits.'}];
        for (const [title,cards,icon] of [['Overview',overview,'mdi:water'],['Usage',usage,'mdi:chart-bar'],['Diagnostics',diagnostic,'mdi:information-outline']])
          views.push({title:`${name} · ${title}`,path:`${device.id}-${title.toLowerCase()}`,icon,cards});
      }
      return {title:'Water Monitor',views:views.length?views:[{title:'Setup',cards:[{type:'markdown',content:'Add the FrizzLife Water Monitor (read only) integration first. Verified volume readings must be enabled during setup for Energy statistics.'}]}]};
    }
  }
  if (!customElements.get('ll-strategy-dashboard-frizzlife-readonly'))
    customElements.define('ll-strategy-dashboard-frizzlife-readonly', FrizzlifeStrategy);
})();
