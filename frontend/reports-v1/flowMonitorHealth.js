// Same threshold the alert center uses (reports_alert_rules.CONSECUTIVE_FAILURES): one bad reading is noise, two is an outage.
export const CONSECUTIVE_FAILURES=2;

/** One row per page of the latest check, with what the recent history says about it. `checks` is newest first. */
export function pageHealth(checks=[]) {
  const latest=checks[0];
  if(!latest?.pages?.length)return [];
  return latest.pages.map(page=>{
    const key=`${page.host}${page.path}`;
    const readings=checks.map(check=>({at:check.checked_at,page:(check.pages||[]).find(item=>`${item.host}${item.path}`===key)})).filter(item=>item.page);
    let failing=0;for(const item of readings){if(item.page.status==='online')break;failing++;}
    const lastFailure=readings.find(item=>item.page.status!=='online');
    const times=readings.map(item=>Number(item.page.duration_ms)).filter(Number.isFinite);
    return {key,label:page.label,host:page.host,path:page.path,status:page.status,http:page.http_status,detail:page.detail,
      responseMs:Number.isFinite(Number(page.duration_ms))?Number(page.duration_ms):null,
      averageMs:times.length?Math.round(times.reduce((sum,value)=>sum+value,0)/times.length):null,
      readings:readings.length,uptime:readings.length?Math.round(1000*readings.filter(item=>item.page.status==='online').length/readings.length)/10:null,
      failing,confirmedDown:failing>=CONSECUTIVE_FAILURES,lastFailureAt:lastFailure?.at||null};
  });
}

/** Failures sort first, then the slowest, so the page that needs attention is on top. */
export const byPriority=(a,b)=>(b.confirmedDown-a.confirmedDown)||(b.failing-a.failing)||((b.responseMs||0)-(a.responseMs||0));
