
(function(){
'use strict';
var d=document,root=d.documentElement;root.classList.add('js');
var idxEl=d.getElementById('dog-index');if(!idxEl)return;
var IDX=JSON.parse(idxEl.textContent),LIST=IDX.dogs||[],DOGS={};
LIST.forEach(function(x){DOGS[x.id]=x});
var B=d.body.dataset,TEL=B.tel,PHONE=B.phone,EMAIL=B.email,HOURS=B.hours;
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
var coarse=window.matchMedia&&matchMedia('(pointer: coarse)').matches;
var UNKNOWN='Unknown — the records don’t say. Ask staff.';
var SIZE={S:'Small',M:'Medium',L:'Large',XL:'Extra large'},BAND={puppy:'Puppy',young:'Young',adult:'Adult',senior:'Senior'};
var GWL={cats:'Cats',dogs:'Other dogs',kids:'Kids'};

function el(tag,cls,text){var x=d.createElement(tag);if(cls)x.className=cls;if(text!=null)x.textContent=text;return x}
function link(href,text,cls){var a=el('a',cls,text);a.href=href;return a}
function mail(subject){return 'mailto:'+EMAIL+'?subject='+encodeURIComponent(subject)}
function labels(sources){var seen={},out=[];(sources||[]).forEach(function(s){var l=s&&s.label;if(l&&!seen[l]){seen[l]=1;out.push(l)}});return out.join(' · ')}
function srcLine(cls,sources){var p=el('p',cls);p.appendChild(el('b',null,'From: '));p.appendChild(d.createTextNode(labels(sources)||'no source on file'));return p}
function gw(dog,k){var g=(dog.good_with||{})[k]||{};return g.value===true?'yes':g.value===false?'no':'unknown'}
function factsOf(dog,topics){return (dog.facts||[]).filter(function(f){return topics.indexOf(f.topic)>=0&&f.sources&&f.sources.length})}
function sinceDate(days){if(days==null||!IDX.reference_date)return null;var p=IDX.reference_date.split('-');return new Date(Date.UTC(+p[0],p[1]-1,+p[2])-days*864e5)}
var MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(dt){return dt?MON[dt.getUTCMonth()]+' '+dt.getUTCDate()+', '+dt.getUTCFullYear():null}
function ageText(x){return x.age_years==null?null:x.age_years===0?'Under 1 year':x.age_years+' year'+(x.age_years===1?'':'s')+' old'}
function feeText(f){return f==null?null:f===0?'Waived':'$'+f}

/* ---------- art: lazy-wake cartoons on screen ---------- */
if('IntersectionObserver' in window){
  root.classList.add('io');
  var io=new IntersectionObserver(function(es){es.forEach(function(en){en.target.classList.toggle('awake',en.isIntersecting)})},{rootMargin:'80px 0px'});
  [].forEach.call(d.querySelectorAll('main .art'),function(a){io.observe(a)});
}
var seq=0;
function ava(id){
  var box=el('span','ava'),src=d.querySelector('main [data-art="'+id+'"]');box.setAttribute('aria-hidden','true');
  if(!src)return box;
  var img=src.querySelector('img');
  if(img){var i=d.createElement('img');i.src=img.getAttribute('src');i.alt='';box.appendChild(i);return box}
  var c=src.cloneNode(true),n='-q'+(++seq);c.removeAttribute('data-art');c.classList.add('awake');
  [].forEach.call(c.querySelectorAll('[id]'),function(x){x.id+=n});
  [].forEach.call(c.querySelectorAll('[clip-path]'),function(x){x.setAttribute('clip-path',x.getAttribute('clip-path').replace(')',n+')'))});
  [].forEach.call(c.querySelectorAll('use'),function(x){x.setAttribute('href',x.getAttribute('href')+n)});
  box.appendChild(c);return box;
}

/* ---------- dialogs: open from a control, give focus back to it on close ---------- */
var openers=new WeakMap();
function openDialog(dlg,from,focusEl){
  from=from||d.activeElement;
  /* focus the opener first: the browser restores focus to whatever was focused
     when showModal() ran, so this makes Esc/close land back on the opener even
     when the opener lives inside another open dialog (Ask inside Compare). */
  if(from&&from.focus&&d.activeElement!==from){try{from.focus({preventScroll:true})}catch(e){}}
  openers.set(dlg,from);
  if(!dlg.open)dlg.showModal();
  if(focusEl)focusEl.focus();
}
function closeDialog(dlg){if(dlg.open)dlg.close()}
[].forEach.call(d.querySelectorAll('dialog'),function(dlg){
  dlg.addEventListener('close',function(){var o=openers.get(dlg);if(o&&o.isConnected&&o.focus){try{o.focus({preventScroll:true})}catch(e){}}});
  dlg.addEventListener('click',function(ev){if(ev.target===dlg)dlg.close()});
  [].forEach.call(dlg.querySelectorAll('[data-close]'),function(b){b.addEventListener('click',function(){dlg.close()})});
});

/* ================= chat ================= */
var chat=d.getElementById('chat');
var CHAT_OK=chat&&typeof chat.showModal==='function';
if(CHAT_OK)root.classList.add('qa');
/* topic id, label, keywords on normalized text, index fact topics, related topics shown when unknown */
var T=[
['cats','Cats',/\b(cats?|kittens?|kitty|kitties|feline)\b/,['cats'],[]],
['dogs','Other dogs',/\b(dogs|other dog|another dog|second dog|dog parks?|play ?groups?|other pups)\b/,['dogs'],[]],
['kids','Kids',/\b(kids?|child|children|toddlers?|baby|babies|infants?|teens?|grandkids?|family|families)\b/,['kids'],[]],
['apartment','Apartment',/\b(apartments?|condos?|small (space|home|place|house)|yards?|flat|studio|townhouse|city)\b/,[],['size','noise','energy','play']],
['house','House training',/\b(housetrained|potty|accidents?|pee|poop|toilet)\b/,['house_training'],['crate']],
['crate','Crate',/\b(crates?|crated|cratetrained)\b/,['crate'],[]],
['energy','Energy',/\b(energy|energetic|active|exercise|run|running|jog|jogging|hikes?|hiking|play|playful|fetch|toys?|ball|lazy|calm|chill|hyper|couch)\b/,['energy','play'],[]],
['noise','Barking',/\b(barks?|barking|barker|noisy|noise|loud|vocal|quiet|howl\w*)\b/,['noise'],[]],
['leash','Leash and walks',/\b(leash|walks?|walking|pull|pulls|pulling|reactive|harness|lunge\w*|jumpy|jump\w*|escape\w*|gates?)\b/,['leash'],[]],
['training','Training',/\b(tricks?|commands?|trained|training|obedien\w*|sit|smart|cues?|manners)\b/,['training'],[]],
['shy','Shy or nervous',/\b(shy|timid|nervous|warm up|warms up|strangers?|new people|first impression)\b/,['shyness'],['fears']],
['fears','Fears',/\b(scared|scary|fears?|afraid|storms?|thunder\w*|fireworks|anxious|anxiety)\b/,['fears'],['shyness']],
['health','Health',/\b(health|healthy|vaccin\w*|shots?|sick|ill|illness|heartworm|medical|meds|medications?|cough|ears?|conditions?|diseases?)\b/,['health','vaccines'],['spay_neuter']],
['vet','Vet visits',/\b(vets?|veterinar\w*)\b/,['vet'],['health']],
['altered','Spayed or neutered',/\b(spay\w*|neuter\w*|fixed|altered|sterili\w*)\b/,['spay_neuter'],[]],
['food','Food',/\b(food|foods|diet|eat|eats|eating|eater|allerg\w*|picky|chicken|feed|feeding|meals?|kibble|treats?)\b/,['food'],[]],
['age','Age',/\b(age|old|young|puppy|senior|birthday)\b/,['age'],[]],
['size','Size',/\b(size|big|small|large|little|tall|tiny|huge|medium)\b/,['size'],[]],
['weight','Weight',/\b(weigh|weighs|weight|pounds?|lbs?|kg|heavy)\b/,[],['size']],
['breed','Breed',/\b(breeds?|mix|mixed|kind of dog|type of dog|what kind|what type)\b/,['breed'],[]],
['color','Color',/\b(colou?rs?|coat|markings?)\b/,['color'],[]],
['sex','Boy or girl',/\b(boy|girl|male|female|sex|gender)\b/,['@sex'],[]],
['fee','Fee',/\$|\b(fees?|costs?|price|pricing|pay|how much)\b/,['fee'],[]],
['since','Time here',/\b(how long|since|been here|arrive\w*|waiting|days)\b/,['here_since','intake'],[]],
['history','Background',/\b(found|stray|history|background|owners?|came in|intake|where (are you|did you come) from|story|transfer\w*|rescued)\b/,['intake'],[]],
['interest','Interest',/\b(interest|interested|popular|anyone else|other people|applications?|applied|asked about)\b/,['interest'],[]],
['meet','How to meet',/\b(meet|visit|adopt|adopting|adoption|apply|appointment|come see|contact|phone|email|next steps?|available|kennel|where are you|how do i)\b/,['meet','location'],[]],
['grooming','Grooming',/\b(groom\w*|shed|sheds|shedding|brush\w*|hypoallergenic|haircuts?|bath\w*)\b/,[],['breed','color']],
['alone','Home alone',/\b(alone|separation|work all day|left home|hours)\b/,[],['crate']],
['pets','Other pets',/\b(rabbits?|bunn(y|ies)|birds?|hamsters?|guinea pigs?|other pets|pets|horses?|livestock|ferrets?|chickens? (coop|yard))\b/,[],['cats','dogs']],
['bite','Biting or guarding',/\b(bites?|biting|bitten|aggress\w*|guard\w*|protective|growl\w*|nips?|nipping)\b/,[],['leash','dogs']],
['car','Car rides',/\b(cars?|car rides?|rides?|travel\w*|road trips?)\b/,[],[]],
['swim','Swimming',/\b(swim\w*|pool|lake|beach)\b/,[],['energy','play']],
['cuddle','Affection',/\b(cuddl\w*|affection\w*|snuggl\w*|lean\w*|velcro|lap ?dog|loving|sweet)\b/,['affection'],['shyness']],
['about','About me',/\b(about you|yourself|personality|temperament|tell me about|describe|friendly|what are you like)\b/,['affection','shyness','play','energy','noise','leash','training','fears','house_training','food','cats','dogs','kids'],[]]
];
var TOPIC={};T.forEach(function(t){TOPIC[t[0]]=t});
function norm(q){
  q=' '+String(q).toLowerCase().replace(/[’']/g,'').replace(/[^a-z0-9$]+/g,' ')+' ';
  return q.replace(/ (house|potty) ?(trained|broken|training) | housebroken /g,' housetrained ')
    .replace(/ (crate|kennel) ?(trained|training) /g,' cratetrained ')
    .replace(/ kennel cough /g,' cough ').replace(/ adoption fees? /g,' fee ')
    .replace(/ dog ?friendly /g,' dogs ').replace(/ cat ?friendly /g,' cats ').replace(/ kid ?friendly /g,' kids ')
    .replace(/ my (\d+|one|two|three|four|five|six|seven|eight|nine|ten) ?(year|yr|month)s? ?olds? /g,' kids ');
}
function topicsFor(q){var n=norm(q),out=[];T.forEach(function(t){if(t[2].test(n))out.push(t[0])});
  /* "apartment ok?" should not also trigger size because of "small apartment" etc.; keep order, drop dups */
  return out}
function gwFact(dog,k){var g=(dog.good_with||{})[k];if(!g||g.value==null||!(g.sources&&g.sources.length))return null;
  return {topic:k,text:'Good with '+(k==='kids'?'kids':k==='dogs'?'other dogs':'cats')+': '+(g.value?'yes':'no')+', per the records.',sources:g.sources}}
function topicFacts(dog,topics){
  var out=[];
  topics.forEach(function(tp){
    if(tp==='@sex'){(dog.facts||[]).forEach(function(f){if(/\b(male|female)\b/i.test(f.text)&&f.sources&&f.sources.length)out.push(f)});return}
    var fs=factsOf(dog,[tp]);
    if(!fs.length&&GWL[tp]){var g=gwFact(dog,tp);if(g)fs=[g]}
    fs.forEach(function(f){
      /* the same sentence from two records shows once, with both labels */
      var same=out.filter(function(o){return o.text.toLowerCase()===f.text.toLowerCase()})[0];
      if(same){if(same!==f)same.sources=(same.sources||[]).concat(f.sources||[])}else out.push({topic:f.topic,text:f.text,sources:(f.sources||[]).slice()});
    });
  });
  return out;
}
function resolve(dog,t){
  var spec=TOPIC[t],fs=topicFacts(dog,spec[3]);
  if(fs.length)return{t:t,facts:fs};
  var rel=[],seen={};
  topicFacts(dog,spec[4]).forEach(function(f){if(!seen[f.text]){seen[f.text]=1;rel.push(f)}});
  return{t:t,unknown:true,facts:rel};
}
var body=d.getElementById('chat-body'),form=d.getElementById('chat-form'),input=d.getElementById('chat-q');
var nameEl=d.getElementById('chat-name'),avaEl=d.getElementById('chat-ava'),title=d.getElementById('chat-title');
var logs={},cur=null;
function botGroup(id){var g=el('div','grp');g.appendChild(ava(id));return g}
function greet(id,log){
  var dog=DOGS[id],g=botGroup(id),m=el('div','msg');
  var twins=LIST.filter(function(x){return x.name===dog.name}).length>1;
  m.appendChild(el('p','msg-a','Hi, I’m '+dog.name+'!'+(twins?' (ID '+id+')':'')+' Ask me anything. I answer only from my shelter records and show where each answer comes from. If they don’t cover something, I’ll say so.'));
  g.appendChild(m);log.appendChild(g);
}
function ctaAsk(dog,id){
  var c=el('p','msg-cta');
  c.appendChild(d.createTextNode('Call '));c.appendChild(link('tel:'+TEL,PHONE));
  c.appendChild(d.createTextNode(' or '));c.appendChild(link(mail('Question about '+dog.name+' ('+id+')'),'email us'));
  return c;
}
function bubble(id,r){
  var dog=DOGS[id],m=el('div','msg');
  m.appendChild(el('p','msg-topic',TOPIC[r.t][1]));
  if(r.unknown&&r.t!=='meet'){
    m.classList.add('warn');
    m.appendChild(el('p','msg-a msg-unk',UNKNOWN));
    if(r.facts.length)m.appendChild(el('p','msg-rel','What the records do say:'));
  }
  r.facts.forEach(function(f){m.appendChild(el('p','msg-a',f.text));m.appendChild(srcLine('msg-src',f.sources))});
  if(r.t==='meet'){
    if(!r.facts.length){m.appendChild(el('p','msg-a','Come say hi: we’re open '+HOURS+'.'));var s=el('p','msg-src');s.appendChild(el('b',null,'From: '));s.appendChild(d.createTextNode('shelter contact info'));m.appendChild(s)}
    var c=el('p','msg-cta');
    c.appendChild(link(mail('Meeting '+dog.name+' ('+id+')'),'Ask to meet '+dog.name,'mbtn'));
    c.appendChild(d.createTextNode(' or call '));c.appendChild(link('tel:'+TEL,PHONE));
    m.appendChild(c);
  }else if(r.unknown){m.appendChild(ctaAsk(dog,id))}
  return m;
}
function fallback(){
  var m=el('div','msg');
  m.appendChild(el('p','msg-a','I couldn’t match that to my records. Try asking about cats, other dogs, kids, apartment living, house training, energy, barking, leash walks, health, food, age, size, my fee, how long I’ve been here or how to meet me.'));
  return m;
}
function reply(id,q){
  var ts=topicsFor(q),n=norm(q);
  if(!ts.length){
    var m=el('div','msg');
    if(/^ (hi|hello|hey|hiya|yo|good (morning|afternoon|evening)) /.test(n))m.appendChild(el('p','msg-a','Hi! What would you like to know about me?'));
    else if(/\b(thanks|thank you|thx|ty)\b/.test(n))m.appendChild(el('p','msg-a','Any time. Come say hi in the yard!'));
    else m=fallback();
    return [m];
  }
  return ts.map(function(t){return bubble(id,resolve(DOGS[id],t))});
}
function scrollToNode(node){body.scrollTop=Math.max(0,node.offsetTop-body.offsetTop-8)}
function ask(q){
  q=String(q||'').trim().slice(0,200);if(!q||!cur)return;
  var id=cur,log=logs[id],me=el('p','msg me',q);
  log.appendChild(me);
  var g=botGroup(id),typing=el('div','msg typing');typing.setAttribute('aria-hidden','true');
  typing.appendChild(el('i'));typing.appendChild(el('i'));typing.appendChild(el('i'));
  g.appendChild(typing);log.appendChild(g);scrollToNode(me);
  var parts=reply(id,q);
  setTimeout(function(){
    typing.remove();
    parts.forEach(function(p,i){if(!reduce)p.style.animationDelay=(i*90)+'ms';g.appendChild(p)});
    scrollToNode(me);
  },reduce?0:380);
}
function openChat(id,from){
  if(!CHAT_OK||!DOGS[id])return;
  cur=id;
  nameEl.textContent=DOGS[id].name;
  avaEl.textContent='';avaEl.appendChild(ava(id));
  for(var k in logs)logs[k].hidden=k!==id;
  if(!logs[id]){var log=el('div','log');log.setAttribute('role','log');log.setAttribute('aria-live','polite');log.setAttribute('aria-label','Conversation with '+DOGS[id].name);logs[id]=log;body.appendChild(log);greet(id,log)}
  input.value='';
  openDialog(chat,from,coarse?title:input);
  body.scrollTop=body.scrollHeight;
}
if(CHAT_OK){
  form.addEventListener('submit',function(ev){ev.preventDefault();ask(input.value);input.value=''});
  [].forEach.call(chat.querySelectorAll('.qchip'),function(b){b.addEventListener('click',function(){ask(b.textContent)})});
  d.getElementById('chat-close').addEventListener('click',function(){chat.close()});
}

/* ================= compare ================= */
var cmp=d.getElementById('cmp'),tray=d.getElementById('ctray');
var picked=[],MAX=3;
function nameOf(id){return DOGS[id].name}
function sync(){
  [].forEach.call(d.querySelectorAll('.tool-cmp'),function(b){b.setAttribute('aria-pressed',picked.indexOf(b.getAttribute('data-dog'))>=0?'true':'false')});
  if(!tray)return;
  var slots=d.getElementById('ctray-slots'),go=d.getElementById('ctray-go');
  slots.textContent='';
  for(var i=0;i<MAX;i++){
    var li=el('li'),id=picked[i];
    if(id){
      li.className='on';
      var b=el('button','slot');b.type='button';b.setAttribute('aria-label','Remove '+nameOf(id)+' ('+id+') from compare');
      b.appendChild(ava(id));var x=el('span','rm');x.innerHTML='<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>';b.appendChild(x);
      b.addEventListener('click',(function(id){return function(){toggle(id)}})(id));li.appendChild(b);
    }
    slots.appendChild(li);
  }
  d.getElementById('ctray-n').textContent=picked.length+'/'+MAX;
  go.disabled=picked.length<2;go.textContent=picked.length<2?'Pick 1 more':'Compare '+picked.length;
  tray.hidden=!picked.length;root.classList.toggle('has-tray',picked.length>0);
  if(cmp.open){if(picked.length)renderCmp();else cmp.close()}
}
function say(t){var msg=d.getElementById('ctray-msg');if(!msg)return;msg.textContent='';setTimeout(function(){msg.textContent=t},30)}
function toggle(id,btn){
  var i=picked.indexOf(id);
  if(i>=0){picked.splice(i,1);say(nameOf(id)+' removed from compare. '+picked.length+' of '+MAX+' picked.')}
  else if(picked.length>=MAX){
    say('You can compare up to '+MAX+' dogs. Remove one first.');
    [btn,tray].forEach(function(x){if(x&&!reduce){x.classList.remove('nope');void x.offsetWidth;x.classList.add('nope')}});
    return;
  }else{picked.push(id);say(nameOf(id)+' added to compare. '+picked.length+' of '+MAX+' picked.')}
  sync();
}
var ROWS=[
 ['Cats',function(x){var g=gw(x,'cats');return g==='unknown'?null:g==='yes'?'Yes':'No'}],
 ['Other dogs',function(x){var g=gw(x,'dogs');return g==='unknown'?null:g==='yes'?'Yes':'No'}],
 ['Kids',function(x){var g=gw(x,'kids');return g==='unknown'?null:g==='yes'?'Yes':'No'}],
 ['House trained',function(x){return x.house_trained===true?'Yes':x.house_trained===false?'Not yet':null}],
 ['Age',function(x){return ageText(x)}],['Size',function(x){return SIZE[x.size]||null}],
 ['Sex',function(x){return x.sex==='M'?'Male':x.sex==='F'?'Female':null}],['Breed',function(x){return x.breed}],
 ['Color',function(x){return x.color}],['Fee',function(x){return feeText(x.fee)}],
 ['Here since',function(x){var s=sinceDate(x.days_on_site);return s?fmtDate(s)+' ('+x.days_on_site+' days)':null}],
 ['Kennel',function(x){return x.location}],
 ['Spayed / neutered',function(x){return x.spay_neuter===true?'Yes':x.spay_neuter===false?'Not yet':null}]
];
function renderCmp(){
  var cols=d.getElementById('cmp-cols');
  cols.textContent='';cols.style.setProperty('--n',picked.length);cols.classList.toggle('one',picked.length<2);
  d.getElementById('cmp-hint').classList.toggle('off',picked.length<2);
  picked.forEach(function(id){
    var dog=DOGS[id],col=el('section','cmp-col');col.setAttribute('aria-label',dog.name+', ID '+id);
    var media=el('div','cmp-media');media.appendChild(ava(id));col.appendChild(media);
    var nm=el('div','cmp-name'),h=el('h3');h.appendChild(link(dog.url,dog.name));nm.appendChild(h);nm.appendChild(el('p',null,'ID '+id));col.appendChild(nm);
    var dl=el('dl');
    ROWS.forEach(function(r){var w=el('div'),dd=el('dd'),v=r[1](dog);w.appendChild(el('dt',null,r[0]));
      if(v==null||v==='')dd.appendChild(el('span','unk','Unknown — ask'));else if(v==='Yes'||v==='No'||v==='Not yet')dd.appendChild(el('span','yn '+(v==='Yes'?'yes':'no'),v));else dd.textContent=v;w.appendChild(dd);dl.appendChild(w)});
    col.appendChild(dl);
    var act=el('div','cmp-act'),a=el('button','tool tool-ask');a.type='button';a.setAttribute('aria-haspopup','dialog');
    a.innerHTML='<svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M3 4.5h14v9H8.5L5 16.5v-3H3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>';
    a.appendChild(el('span',null,'Ask '+dog.name));a.setAttribute('data-cmp-ask',id);
    a.addEventListener('click',function(){openChat(id,a)});
    act.appendChild(a);
    act.appendChild(link(mail('Meeting '+dog.name+' ('+id+')'),'Ask to meet'));
    var rm=el('button','rm2','Remove');rm.type='button';rm.setAttribute('aria-label','Remove '+dog.name+' from compare');
    rm.addEventListener('click',function(){toggle(id);if(cmp.open&&picked.length)d.getElementById('cmp-title').focus()});
    act.appendChild(rm);col.appendChild(act);
    cols.appendChild(col);
  });
}
if(tray&&cmp){
  var go=d.getElementById('ctray-go');
  go.addEventListener('click',function(){if(picked.length<2)return;renderCmp();openDialog(cmp,go,d.getElementById('cmp-title'));d.getElementById('cmp-cols').scrollLeft=0});
  d.getElementById('ctray-clear').addEventListener('click',function(){picked=[];say('Compare cleared.');sync()});
  d.getElementById('cmp-close').addEventListener('click',function(){cmp.close()});
}
/* every Ask / Compare button on the page (cards, ranking, dog page) */
d.addEventListener('click',function(ev){
  var b=ev.target.closest&&ev.target.closest('.tools .tool');if(!b)return;
  var id=b.getAttribute('data-dog');if(!id)return;
  if(b.classList.contains('tool-ask'))openChat(id,b);else toggle(id,b);
});

/* ================= search + filters ================= */
var grid=d.getElementById('grid');
if(grid){
  var q=d.getElementById('q'),sortSel=d.getElementById('sort'),keep=d.getElementById('keep'),countEl=d.getElementById('count');
  var fbtn=d.getElementById('fbtn'),filters=d.getElementById('filters'),fn=d.getElementById('fn'),empty=d.getElementById('empty');
  var cards={};[].forEach.call(grid.children,function(li){cards[li.getAttribute('data-id')]=li});
  var F={size:[],age:[],cats:[],dogs:[],kids:[]};
  function words(s){return String(s||'').toLowerCase().replace(/[’']/g,'').replace(/[^a-z0-9]+/g,' ').trim()}
  var HAY={};LIST.forEach(function(x){HAY[x.id]=' '+words([x.search,x.name].concat(x.aliases||[],[x.breed,x.color,x.id]).join(' '))+' '});
  function passes(x,tokens){
    for(var i=0;i<tokens.length;i++){if(HAY[x.id].indexOf(' '+tokens[i])<0)return false}
    if(F.size.length&&F.size.indexOf(x.size||'')<0&&!(x.size==null&&keep.checked))return false;
    var band=x.age_band||'unknown';
    if(F.age.length&&F.age.indexOf(band)<0&&!(band==='unknown'&&keep.checked))return false;
    var kept=[];   /* filters this dog passes only because unknowns are kept */
    for(var k in GWL){if(!F[k].length)continue;var v=gw(x,k);
      if(F[k].indexOf(v)>=0)continue;
      if(v==='unknown'&&keep.checked){kept.push(k);continue}
      return false}
    return kept;
  }
  var SORTS={
    stay:function(a,b){return (b.days_on_site||0)-(a.days_on_site||0)||a.name.localeCompare(b.name)||a.id.localeCompare(b.id)},
    name:function(a,b){return a.name.localeCompare(b.name)||a.id.localeCompare(b.id)},
    young:function(a,b){var x=a.age_years==null?99:a.age_years,y=b.age_years==null?99:b.age_years;return x-y||a.name.localeCompare(b.name)},
    fee:function(a,b){var x=a.fee==null?1e9:a.fee,y=b.fee==null?1e9:b.fee;return x-y||a.name.localeCompare(b.name)}
  };
  var liveT=null;
  function apply(announce){
    var tokens=words(q.value).split(' ').filter(Boolean),shown=0,active=0;
    for(var k in F)active+=F[k].length;
    var order=LIST.slice().sort(SORTS[sortSel.value]||SORTS.stay);
    order.forEach(function(x){
      var li=cards[x.id];if(!li)return;
      var r=passes(x,tokens);li.hidden=!r;if(r)shown++;
      [].forEach.call(li.querySelectorAll('.gw .gw-unknown'),function(c){c.classList.toggle('hit',!!r&&c.getAttribute('data-gw').split(' ').some(function(k){return r.indexOf(k)>=0}))});
      grid.appendChild(li);
    });
    fn.hidden=!active;fn.textContent=active;
    empty.hidden=shown>0;
    var t=shown===LIST.length?'Showing all '+shown+' dogs':'Showing '+shown+' of '+LIST.length+' dogs';
    clearTimeout(liveT);liveT=setTimeout(function(){countEl.textContent=t},announce?350:0);
  }
  [].forEach.call(filters.querySelectorAll('.chip'),function(c){
    c.addEventListener('click',function(){
      var g=c.getAttribute('data-f'),v=c.getAttribute('data-v'),arr=F[g],i=arr.indexOf(v);
      if(i>=0)arr.splice(i,1);else arr.push(v);
      c.setAttribute('aria-pressed',i>=0?'false':'true');apply();
    });
  });
  function clearAll(){for(var k in F)F[k]=[];[].forEach.call(filters.querySelectorAll('.chip'),function(c){c.setAttribute('aria-pressed','false')});keep.checked=true;q.value='';apply()}
  q.addEventListener('input',function(){apply(true)});
  sortSel.addEventListener('change',function(){apply()});
  keep.addEventListener('change',function(){apply()});
  d.getElementById('clear').addEventListener('click',clearAll);
  d.getElementById('empty-clear').addEventListener('click',function(){clearAll();q.focus()});
  fbtn.addEventListener('click',function(){var o=fbtn.getAttribute('aria-expanded')!=='true';fbtn.setAttribute('aria-expanded',o);filters.classList.toggle('open',o)});
  apply();
}

/* ================= ranking (Find my match + guide shortlist) ================= */
function rank(ans){
  return LIST.map(function(x){
    var pts=[],score=0;
    function add(n,label,text,sources,kind){pts.push({n:n,label:label,text:text,sources:sources||[],kind:kind});score+=n}
    ['cats','dogs','kids'].forEach(function(k){
      if(ans[k]!=='yes')return;
      var g=(x.good_with||{})[k]||{},fs=factsOf(x,[k]),lab=k==='cats'?'Cats at home':k==='dogs'?'Other dogs at home':'Kids at home';
      var src=(g.sources&&g.sources.length)?g.sources:(fs[0]&&fs[0].sources);
      var txt=fs.length?fs.map(function(f){return f.text}).join(' '):null;
      if(g.value===true&&src&&src.length)add(2,lab,txt||'The records say yes.',src,'pos');
      else if(g.value===false&&src&&src.length)add(-3,lab,txt||'The records say no.',src,'neg');
      else add(0,lab,'Unknown — the records don’t give a yes or no.'+(txt?' On file: '+txt:''),fs.length?[].concat.apply([],fs.map(function(f){return f.sources})):[],'ask');
    });
    if(ans.sizes.length){
      var sf=factsOf(x,['size'])[0],sw=SIZE[x.size];
      if(!x.size||!sf)add(0,'Size','Unknown — no sourced size on file.',[],'ask');
      else if(ans.sizes.indexOf(x.size)>=0)add(1,'Size',sw+', one you picked.',sf.sources,'pos');
      else add(-1,'Size',sw+', not one you picked.',sf.sources,'neg');
    }
    if(ans.ages.length){
      var af=factsOf(x,['age'])[0],bd=x.age_band;
      if(!bd||bd==='unknown'||!af)add(0,'Age','Unknown — no sourced age on file.',[],'ask');
      else if(ans.ages.indexOf(bd)>=0)add(1,'Age',BAND[bd]+': '+af.text,af.sources,'pos');
      else add(-1,'Age',BAND[bd]+': '+af.text,af.sources,'neg');
    }
    if(ans.ht==='yes'){
      var hf=factsOf(x,['house_training']);
      if(x.house_trained===true&&hf.length)add(2,'House trained',hf[0].text,hf[0].sources,'pos');
      else if(x.house_trained===false&&hf.length)add(-2,'House trained',hf[0].text,hf[0].sources,'neg');
      else add(0,'House trained','Unknown — the records don’t say.',[],'ask');
    }
    return {dog:x,score:score,pts:pts};
  }).sort(function(a,b){return b.score-a.score||(b.dog.days_on_site||0)-(a.dog.days_on_site||0)||a.dog.name.localeCompare(b.dog.name)||a.dog.id.localeCompare(b.dog.id)});
}
function resultCard(r){
  var x=r.dog,li=el('li','rcard');
  li.appendChild(ava(x.id));
  var top=el('div','rtop'),h=el('h3','rname');h.appendChild(link(x.url,x.name));h.appendChild(el('small',null,'ID '+x.id));top.appendChild(h);
  var sc=el('span','rscore'+(r.score>0?' pos':r.score<0?' neg':''),(r.score>0?'+':r.score<0?'−':'')+Math.abs(r.score)+' point'+(Math.abs(r.score)===1?'':'s'));
  top.appendChild(sc);
  var meta=el('p',null,[ageText(x),SIZE[x.size],x.breed].filter(Boolean).join(' · '));meta.style.margin='4px 0 0';meta.style.fontSize='14px';meta.style.color='var(--ink-2)';
  var wrap=el('div');wrap.appendChild(top);wrap.appendChild(meta);li.appendChild(wrap);
  var ul=el('ul','pts');
  if(!r.pts.length){var e=el('li');e.appendChild(el('span','pt pt-ask','0'));e.appendChild(el('p',null,'Nothing to score yet: answer a question or two.'));ul.appendChild(e)}
  r.pts.forEach(function(p){
    var it=el('li');
    it.appendChild(el('span','pt pt-'+p.kind,p.kind==='ask'?'0 · ask':(p.n>0?'+':'−')+Math.abs(p.n)));
    it.appendChild(el('b',null,p.label));
    it.appendChild(el('p',null,p.text));
    if(p.sources.length)it.appendChild(srcLine('src',p.sources));
    else if(p.kind==='ask'){var s=el('p','src');s.appendChild(el('b',null,'Ask: '));s.appendChild(link('tel:'+TEL,PHONE));it.appendChild(s)}
    ul.appendChild(it);
  });
  li.appendChild(ul);
  var tools=el('div','tools');
  var a=el('button','tool tool-ask');a.type='button';a.setAttribute('data-dog',x.id);a.setAttribute('aria-haspopup','dialog');a.appendChild(el('span',null,'Ask '+x.name));
  var c=el('button','tool tool-cmp');c.type='button';c.setAttribute('data-dog',x.id);c.setAttribute('aria-pressed',picked.indexOf(x.id)>=0?'true':'false');
  var bx=el('span','box');bx.setAttribute('aria-hidden','true');c.appendChild(bx);c.appendChild(el('span',null,'Compare'));
  tools.appendChild(a);if(tray)tools.appendChild(c);li.appendChild(tools);
  return li;
}
function checked(form,name){return [].map.call(form.querySelectorAll('input[name="'+name+'"]:checked'),function(i){return i.value})}
var match=d.getElementById('match');
if(match){
  var mform=d.getElementById('match-form'),results=d.getElementById('match-results'),rlist=d.getElementById('rlist'),rmore=d.getElementById('rmore'),mtitle=d.getElementById('match-title');
  var lastRank=[];
  function showRank(list,all){
    rlist.textContent='';(all?list:list.slice(0,8)).forEach(function(r){rlist.appendChild(resultCard(r))});
    rmore.hidden=all||list.length<=8;
  }
  function answersFrom(form,p){
    return {cats:checked(form,p+'-cats')[0],dogs:checked(form,p+'-dogs')[0],kids:checked(form,p+'-kids')[0],
      sizes:checked(form,p+'-size').filter(Boolean),ages:checked(form,p+'-age').filter(Boolean),ht:checked(form,p+'-ht')[0]};
  }
  function runMatch(ans){
    lastRank=rank(ans);showRank(lastRank,false);
    mform.hidden=true;results.hidden=false;mtitle.textContent='Your ranked dogs';
    var top=lastRank[0];
    d.getElementById('match-live').textContent='Ranked '+lastRank.length+' dogs. Top: '+(top?top.dog.name:'none')+'.';
    mtitle.focus();d.querySelector('#match .sheet-body').scrollTop=0;
  }
  mform.addEventListener('submit',function(ev){ev.preventDefault();runMatch(answersFrom(mform,'m'))});
  d.getElementById('match-edit').addEventListener('click',function(){results.hidden=true;mform.hidden=false;mtitle.textContent='What’s your home like?';mtitle.focus()});
  rmore.addEventListener('click',function(){showRank(lastRank,true);rmore.hidden=true});
  match.addEventListener('click',function(){setTimeout(sync,0)});
  window.__runMatch=runMatch;
}
/* guide */
var guide=d.getElementById('guide');
if(guide){
  var gform=d.getElementById('guide-form'),steps=[].slice.call(gform.querySelectorAll('.gstep')),gi=0;
  var gback=d.getElementById('gback'),gnext=d.getElementById('gnext'),prog=d.getElementById('guide-prog'),fill=d.getElementById('guide-fill');
  function show(i){
    gi=i;steps.forEach(function(s,j){s.hidden=j!==i});
    var last=i===steps.length-1,lastQ=i===steps.length-2;
    prog.textContent=last?'All done':'Step '+(i+1)+' of '+(steps.length-1);
    d.getElementById('guide-title').textContent=last?'Here\u2019s where to start':'Let\u2019s figure out what you need';
    fill.style.width=(last?100:(i+1)/(steps.length-1)*100)+'%';
    gback.style.visibility=i===0?'hidden':'visible';
    gnext.firstChild.nodeValue=last?'See the full ranking ':lastQ?'See my shortlist ':'Next ';
    var h=steps[i].querySelector('h3');if(h)h.focus();
    d.querySelector('#guide .sheet-body').scrollTop=0;
  }
  function guideAnswers(){
    var size=checked(gform,'g-size')[0],age=checked(gform,'g-age')[0];
    return {cats:checked(gform,'g-cats')[0],dogs:checked(gform,'g-dogs')[0],kids:checked(gform,'g-kids')[0],
      sizes:size?[size]:[],ages:age?[age]:[],ht:checked(gform,'g-ht')[0],
      home:checked(gform,'g-home')[0],alone:checked(gform,'g-alone')[0],energy:checked(gform,'g-energy')[0]};
  }
  function shortlist(){
    var a=guideAnswers(),r=rank(a),gl=d.getElementById('glist'),ga=d.getElementById('gask');
    gl.textContent='';r.slice(0,5).forEach(function(x){gl.appendChild(resultCard(x))});
    ga.textContent='';
    var asks=[];
    if(a.home==='apt')asks.push('Apartment life: no record rates this. Ask about barking and how each dog settles indoors.');
    if(a.home==='yard')asks.push('Yards: a few records mention gates or digging. Ask how each dog does in a yard.');
    if(a.cats==='yes')asks.push('Cats: most records don’t say. Ask whether a cat test can be set up.');
    if(a.dogs==='yes')asks.push('Your dog: ask about a meet-and-greet with your dog at the shelter.');
    if(a.kids==='yes')asks.push('Kids: the records almost never say. Ask staff what they have seen.');
    if(a.alone)asks.push('Time alone ('+({short:'under 4 hours',mid:'4 to 8 hours',long:'more than 8 hours'})[a.alone]+'): no record covers this. Ask staff how each dog does when left.');
    if(a.energy)asks.push('Energy: it isn’t scored. Ask what each dog is like in the play yard.');
    if(!asks.length)asks.push('Anything marked “ask” on your shortlist.');
    asks.forEach(function(t){ga.appendChild(el('li',null,t))});
    window.__guideRank=a;
  }
  gnext.addEventListener('click',function(){
    if(gi===steps.length-2){shortlist();show(gi+1);return}
    if(gi===steps.length-1){
      var a=window.__guideRank;guide.close();
      /* mirror the guide's answers into the match form, then rank there */
      var m=d.getElementById('match-form');
      ['cats','dogs','kids','ht'].forEach(function(k){var i=m.querySelector('input[name="m-'+k+'"][value="'+(a[k]||'no')+'"]');if(i)i.checked=true});
      [].forEach.call(m.querySelectorAll('input[name="m-size"],input[name="m-age"]'),function(i){i.checked=a.sizes.indexOf(i.value)>=0||a.ages.indexOf(i.value)>=0});
      openDialog(match,d.querySelector('[data-open="guide"]'));window.__runMatch(a);return;
    }
    show(gi+1);
  });
  gback.addEventListener('click',function(){if(gi>0)show(gi-1)});
  guide.addEventListener('close',function(){setTimeout(sync,0)});
  window.__guideShow=show;
}
[].forEach.call(d.querySelectorAll('[data-open]'),function(b){
  b.addEventListener('click',function(){
    var dlg=d.getElementById(b.getAttribute('data-open'));if(!dlg||typeof dlg.showModal!=='function')return;
    if(dlg===guide)window.__guideShow&&setTimeout(function(){window.__guideShow(0)},0);
    if(dlg===match){d.getElementById('match-results').hidden=true;d.getElementById('match-form').hidden=false;d.getElementById('match-title').textContent='What’s your home like?'}
    openDialog(dlg,b,dlg.querySelector('h2'));
  });
});
sync();
})();
