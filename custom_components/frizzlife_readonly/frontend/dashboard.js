/* Registry-based native Lovelace dashboard. No service calls or valve controls. */
(() => {
  const domain = 'frizzlife_readonly';
  const labels = {pressure:'Water pressure · psi',pressure_bar:'Water pressure · bar',flow:'Live flow',water_today:'Water used today',
    reported_104:'DP104 raw reading',valve_position:'Valve position',protection:'Protection',
    leak_warning:'Leak warning',leak_alarm:'Leak alarm',faults:'Reported fault bitmap',
    pressure_raw:'Pressure raw reading',measurement_units:'Reported measurement units',last_poll:'Last successful local poll',
    mode_group:'Protection mode group',smart_mode:'Configured smart mode',pro_mode:'Configured pro mode',
    low_flow_enabled:'Low-flow protection enabled',low_flow_code:'Low-flow threshold code',
    mode4_time_raw:'Mode 4 alarm time raw',mode5_time_raw:'Mode 5 alarm time raw',mode6_time_raw:'Mode 6 alarm time raw',
    mode4_flow_code:'Mode 4 flow threshold code',mode5_flow_code:'Mode 5 flow threshold code',mode6_flow_code:'Mode 6 flow threshold code',
    fault_power:'Power failure',fault_empty_pipe:'Empty pipe',fault_backflow:'Reverse flow',fault_overrange:'Over-range fault',
    fault_temperature:'Temperature fault',fault_hardware:'Hardware fault',fault_valve_stuck:'Stuck valve',
    leak_duration_raw:'Leak-event duration raw',leak_volume_raw:'Leak-event volume raw',
    warning_duration_raw:'Warning-event duration raw',warning_volume_raw:'Warning-event volume raw',test_remaining_raw:'Test remaining time raw',
    comparison_status:'Comparison status',comparison_result:'Indicative result',sample_days:'Full days included',
    average_daily_litres:'Average daily water (L/day)',projected_annual_m3:'Projected annual water use',
    current_annual_bill:'Current annual unmetered bill',projected_annual_cost:'Estimated annual metered cost',
    projected_monthly_cost:'Estimated monthly metered cost',projected_annual_saving:'Estimated annual saving',
    break_even_daily_litres:'Break-even water use (L/day)',today_metered_cost:'Estimated metered cost today',
    annual_standing:'Annual standing charge',water_rate:'Water rate',sewer_rate:'Sewerage rate',effective_rate:'Effective combined rate',
    tariff_status:'Tariff update status',tariff_valid_until:'Tariff valid until',tariff_last_checked:'Last successful catalogue check'};
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
          group('Live readings',['pressure','pressure_bar','flow','water_today']),
          group('Monitor status',['valve_position','protection','leak_warning','leak_alarm']),
          history('Pressure · last 24 hours',['pressure']),history('Flow · last 24 hours',['flow'])];
        const usage = [{type:'markdown',content:'## Water usage\nThe device reports a daily counter, which resets at midnight. Home Assistant records its increases across resets. Select **Water used today** as the water source in Energy. History starts when Recorder first sees this entity; previous app history is not imported.'},
          group('Reported consumption',['water_today'])];
        if (map.water_today) usage.push({type:'statistics-graph',title:'Daily water use · 14 days',
          chart_type:'bar',period:'day',days_to_show:14,stat_types:['change'],entities:[map.water_today]});
        const diagnostic = [group('Reported device data',['last_poll','pressure_raw','measurement_units','faults','reported_104']),
          group('Reported fault flags',['fault_power','fault_empty_pipe','fault_backflow','fault_overrange','fault_temperature','fault_hardware','fault_valve_stuck']),
          group('Protection configuration',['mode_group','smart_mode','pro_mode','low_flow_enabled','low_flow_code','mode4_time_raw','mode5_time_raw','mode6_time_raw','mode4_flow_code','mode5_flow_code','mode6_flow_code']),
          group('Unverified event and test readings',['leak_duration_raw','leak_volume_raw','warning_duration_raw','warning_volume_raw','test_remaining_raw']),
          {type:'markdown',content:'Protection settings are displayed as reported, with no controls. Mode numbers and threshold codes have no assumed physical meaning. Raw event/time values have unverified units and may be retained or inactive values. Fault names follow the vendor bitmap; a temperature fault flag does not imply this pressure model has a working temperature sensor.'},
          {type:'markdown',content:'This integration reads local status every 30 seconds. It provides no valve, reset, pairing or protection commands. Missing readings are unavailable. The raw fault bitmap is zero when the monitor reports no fault bits.'}];
        const comparison = [
          {type:'markdown',content:'## Would a water meter cost less?\nConfigure **Water meter cost comparison** in the [integration options](/config/integrations/integration/frizzlife_readonly). Select your region/supplier tariff and enter your annual unmetered bill when known. A zero bill means unknown.\n\nEstimates use recorded full hourly days, excluding today and the first observed day. Annual estimates need at least one full day; the indicative result waits for seven. A longer period helps account for seasonal water use. The monitor must cover the whole supply, including any garden taps. This is an estimate, not a supplier quote.'},
          group('Comparison basis',['comparison_status','sample_days','average_daily_litres','projected_annual_m3']),
          group('Metered versus unmetered',['current_annual_bill','projected_annual_cost','projected_monthly_cost','projected_annual_saving','break_even_daily_litres','comparison_result','today_metered_cost']),
          group('Tariff and update status',['annual_standing','water_rate','sewer_rate','effective_rate','tariff_status','tariff_valid_until','tariff_last_checked']),
          {type:'markdown',content:'Rates are applied at today’s tariff across a 365-day projection. Welsh Water presets cover standard household water/sewerage, approved surface-water rebates, or water only. The usual sewer-return allowance is 95%; special low-volume billing, social tariffs, discounts and individual allowances can differ. Missing statistic hours are excluded, but short monitoring gaps can still affect estimates.\n\nAutomatic pricing checks download a maintained tariff catalogue daily. They do not scrape an official live feed. Expired tariffs stop producing estimates. Other suppliers currently use manually entered custom rates.'}];
        for (const [title,cards,icon] of [['Overview',overview,'mdi:water'],['Usage',usage,'mdi:chart-bar'],['Diagnostics',diagnostic,'mdi:information-outline'],['Meter comparison',comparison,'mdi:currency-gbp']])
          views.push({title:`${name} · ${title}`,path:`${device.id}-${title.toLowerCase()}`,icon,cards});
      }
      return {title:'Water Monitor',views:views.length?views:[{title:'Setup',cards:[{type:'markdown',content:'Add the FrizzLife Water Monitor (read only) integration first. Verified volume readings must be enabled during setup for Energy statistics.'}]}]};
    }
  }
  if (!customElements.get('ll-strategy-dashboard-frizzlife-readonly'))
    customElements.define('ll-strategy-dashboard-frizzlife-readonly', FrizzlifeStrategy);
})();
