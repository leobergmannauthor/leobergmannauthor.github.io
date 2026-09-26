const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../assets/analytics.js'),'utf8');
function page(saved=null,host='leobergmannauthor.github.io',brokenStorage=false) {
  const handlers={}, windowHandlers={}, nodes={}, tags=[], cookies=[];
  let stored=saved, reloads=0;
  for (const name of ['banner','settings','accept','reject']) nodes[name]={hidden:true,addEventListener:(event,fn)=>handlers[name]=fn,focus(){},querySelector(){return nodes.reject;}};
  const window={addEventListener:(name,fn)=>windowHandlers[name]=fn};
  const document={
    currentScript:{dataset:{measurementId:'G-TEST123',siteHost:'leobergmannauthor.github.io'}},
    referrer:'https://www.pinterest.com/pin/123/?email=private',
    querySelector(selector){
      if(selector==='[data-book-id]') return {dataset:{bookId:'001_protein',recipeId:'recipe_030'}};
      return nodes[selector.replace('[data-analytics-','').replace(']','')];
    },
    createElement(){return {};}, head:{appendChild:tag=>tags.push(tag)},
    addEventListener:(name,fn)=>handlers[name]=fn
  };
  Object.defineProperty(document,'cookie',{get:()=> '_ga=old; _ga_TEST123=old; preference=keep',set:value=>cookies.push(value)});
  const location={origin:'https://'+host,hostname:host,pathname:'/rezepte/demo.html',search:'?utm_source=pinterest&utm_content=001_protein:recipe_030:photo&email=private',href:'https://'+host+'/rezepte/demo.html',reload:()=>reloads++};
  const localStorage={getItem(){if(brokenStorage)throw Error('disabled');return stored;},setItem(key,value){if(brokenStorage)throw Error('disabled');stored=value;}};
  vm.runInNewContext(source,{window,document,location,localStorage,URL,URLSearchParams,Date});
  return {window,nodes,tags,handlers,windowHandlers,cookies,get reloads(){return reloads;},get stored(){return JSON.parse(stored);}};
}
const choice = (allowed,expires=Date.now()+86400000)=>JSON.stringify({allowed,expires});
test('no Google download or events before consent',()=>{
 const p=page();assert.equal(p.tags.length,0);assert.equal(p.window.dataLayer,undefined);assert.equal(p.nodes.banner.hidden,false);
});
test('reject stores choice without loading Google',()=>{
 const p=page();p.handlers.reject();assert.equal(p.tags.length,0);assert.equal(p.stored.allowed,false);assert.equal(p.nodes.banner.hidden,true);
 assert(p.cookies.every(c=>c.startsWith('_ga')));
});
test('grant loads once, denies ads and strips private query/referrer data',()=>{
 const p=page();p.handlers.accept();p.handlers.accept();assert.equal(p.tags.length,1);
 const calls=p.window.dataLayer.map(x=>Array.from(x));
 assert.equal(calls[0][2].analytics_storage,'denied');assert.equal(calls[1][2].analytics_storage,'granted');assert.equal(calls[1][2].ad_user_data,'denied');
 const config=calls.find(c=>c[0]==='config')[2];assert(!config.page_location.includes('email'));assert.equal(config.page_referrer,'https://www.pinterest.com');assert.equal(config.pin_variant,'photo');
});
test('Amazon click sends book, recipe and placement only after opt-in',()=>{
 const p=page();const link={href:'https://www.amazon.de/dp/B0G1KMD28S?private=no',closest:s=>s==='.book-offer'?{}:null};
 const event={target:{closest:()=>link}};p.handlers.click(event);assert.equal(p.window.dataLayer,undefined);
 p.handlers.accept();p.handlers.click(event);const evt=Array.from(p.window.dataLayer.at(-1));
 assert.equal(evt[1],'amazon_click');assert.equal(evt[2].book_id,'001_protein');assert.equal(evt[2].cta_position,'book_offer');assert.equal(evt[2].link_url,'https://www.amazon.de/dp/B0G1KMD28S');
});
test('withdrawal disables measurement and reloads without changing unrelated cookies',()=>{
 const p=page(choice(true));p.handlers.reject();assert.equal(p.window['ga-disable-G-TEST123'],true);assert.equal(p.reloads,1);assert(p.cookies.every(x=>!x.includes('preference')));
});
test('expired or broken storage requires consent again',()=>{
 for(const p of [page(choice(true,0)),page(null,undefined,true)]){assert.equal(p.tags.length,0);assert.equal(p.nodes.banner.hidden,false);p.handlers.accept();assert.equal(p.tags.length,1);}
});
test('local preview never sends to the live property',()=>{const p=page(choice(true),'localhost');assert.equal(p.tags.length,0);});
test('saved denial and cross-tab withdrawal remain respected',()=>{
 const p=page(choice(false));assert.equal(p.tags.length,0);assert.equal(p.nodes.banner.hidden,true);
 const q=page(choice(true));q.handlers.reject();q.windowHandlers.storage({key:'leo_analytics_consent_v1'});assert.equal(q.window['ga-disable-G-TEST123'],true);
});
