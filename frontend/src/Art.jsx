import React, { useId, useState } from 'react';
export function Icon({name, size=20, ...props}) {
  const paths = {
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    bag: <><path d="M5 7h14l1 14H4L5 7Z"/><path d="M8 8V6a4 4 0 0 1 8 0v2"/></>,
    arrow: <><path d="M4 12h16M14 6l6 6-6 6"/></>,
    heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>,
    close: <path d="m6 6 12 12M6 18 18 6"/>,
    check: <path d="m5 12 4 4L19 6"/>,
    book: <><path d="M12 5C8 2 3 3 3 3v16s5-1 9 2c4-3 9-2 9-2V3s-5-1-9 2Z"/><path d="M12 5v16"/></>,
    pen: <><path d="m16 3 5 5-12 12-6 1 1-6L16 3Z"/><path d="m13 6 5 5"/></>,
    spark: <><path d="m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z"/></>,
    cube: <><path d="m12 2 9 5v10l-9 5-9-5V7l9-5Z"/><path d="m3 7 9 5 9-5M12 12v10"/></>,
    leaf: <><path d="M20 3C8 2 3 8 5 15c7 5 15 1 15-12Z"/><path d="m3 21 12-12"/></>,
    shield: <><path d="m12 2 8 3v6c0 6-8 11-8 11S4 17 4 11V5l8-3Z"/><path d="m8 11 3 3 5-5"/></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name]||paths.bag}</svg>;
}
export function ProductArt({type='bag', className='', images=[]}) {
  const [failed,setFailed]=useState(false);
  const image=images?.[0];
  const id=useId().replaceAll(':','');
  if(image&&!failed)return <img className={'catalog-photo '+className} src={image} alt={type+' product'} onError={()=>setFailed(true)} loading="lazy"/>;
  return <svg className={className} viewBox="0 0 300 260" role="img" aria-label={`${type} product illustration`}>
    <defs><linearGradient id={id} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#435d77"/><stop offset="1" stopColor="#15263b"/></linearGradient><filter id={id+'shadow'} x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter></defs>
    <ellipse cx="150" cy="222" rx="68" ry="10" fill="#111b30" opacity=".12" filter={`url(#${id}shadow)`}/>
    {type==='headphones'&&<g><path d="M90 155V110a60 60 0 0 1 120 0v45" fill="none" stroke="#334763" strokeWidth="20"/><path d="M90 113a60 60 0 0 1 120 0" fill="none" stroke="#677e99" strokeWidth="7"/><rect x="76" y="127" width="32" height="71" rx="14" fill="#172d46"/><rect x="192" y="127" width="32" height="71" rx="14" fill="#172d46"/><path d="M198 139v43M100 139v43" stroke="#a4b58a" strokeWidth="3"/></g>}
    {type==='hoodie'&&<g><path d="m110 72-38 23-30 86 35 16 26-59v72h94v-72l26 59 35-16-30-86-38-23Z" fill="#657386"/><path d="M111 72q-4-49 39-49 43 0 39 49l-39 30Z" fill="#3c4f68"/><path d="m136 85 4 34m24-34-4 34" stroke="#d8e5b8" strokeWidth="3"/><path d="m124 162-9 25h70l-9-25Z" fill="#516177"/><text x="150" y="143" textAnchor="middle" fill="#d8e5b8" fontSize="13" fontFamily="sans-serif">CAMPUS</text></g>}
    {type==='mug'&&<g><path d="M191 94h16q48 0 37 50-8 23-49 18" fill="none" stroke="#afbf83" strokeWidth="15"/><path d="M84 84h116v95q0 39-58 39-58 0-58-39Z" fill="#becd98"/><ellipse cx="142" cy="84" rx="58" ry="12" fill="#dde6c6"/><text x="142" y="149" textAnchor="middle" fill="#394b32" fontSize="12" fontFamily="sans-serif">CAMPUS</text><text x="142" y="170" textAnchor="middle" fill="#394b32" fontSize="8" fontFamily="sans-serif">GOOD DAYS AHEAD</text></g>}
    {type==='tech'&&<g transform="rotate(-12 150 130)"><rect x="100" y="42" width="99" height="177" rx="14" fill="#314861"/><rect x="111" y="57" width="77" height="44" rx="4" fill="#b3c4a4"/><text x="178" y="87" textAnchor="end" fill="#324233" fontSize="14">3.14159</text>{Array.from({length:20},(_,i)=><rect key={i} x={112+i%4*19} y={116+Math.floor(i/4)*17} width="13" height="10" rx="3" fill={i%4===3?'#b6cb80':'#768da2'}/>)}</g>}
    {type==='goggles'&&<g><path d="M55 108q90-30 190 0v52q-42 39-84-8h-22q-40 47-84 8Z" fill="#b4d5dc" opacity=".7" stroke="#4b6980" strokeWidth="8"/><path d="M50 117 24 95m226 22 26-22" stroke="#334861" strokeWidth="12"/><path d="M70 121h48M180 121h44" stroke="white" strokeWidth="7" opacity=".7"/></g>}
    {type==='bag'  && <g transform="rotate(-8 150 130)"><path d="M128 51V40q22-20 44 0v11" fill="none" stroke="#253849" strokeWidth="10"/><path d="M88 92q-14 48-3 103M212 92q14 48 3 103" fill="none" stroke="#304456" strokeWidth="12"/><rect x="91" y="48" width="118" height="161" rx="35" fill={`url(#${id})`}/><path d="M106 82q44-29 88 0" stroke="#7891a4" strokeWidth="2" fill="none"/><rect x="108" y="122" width="85" height="70" rx="14" fill="#30455b"/><path d="M114 135h73" stroke="#96a8b8" strokeWidth="2"/><path d="M183 133v10" stroke="#d1dbad" strokeWidth="3"/><rect x="132" y="95" width="36" height="13" rx="3" fill="#d9eea9"/><text x="150" y="105" textAnchor="middle" fontSize="6" fontFamily="sans-serif" fill="#172b34">CAMPUS</text></g>}
    {type==='bottle' && <g transform="rotate(10 150 130)"><rect x="126" y="35" width="48" height="28" rx="9" fill="#213d35"/><rect x="113" y="59" width="74" height="158" rx="24" fill="#86a89a"/><rect x="122" y="65" width="8" height="132" rx="4" fill="#c3dbce" opacity=".55"/><path d="M146 147q-20-18 5-35 22 12 5 30" fill="none" stroke="#e0efdc" strokeWidth="3"/><path d="M143 154l13-28" stroke="#e0efdc" strokeWidth="2"/></g>}
    {['book','notebook','planner'].includes(type) && <g transform="rotate(-12 150 130)"><rect x="90" y="50" width="125" height="171" rx="6" fill="#d0cbb9"/><rect x="81" y="42" width="126" height="172" rx="6" fill={type==='book'?'#314b69':type==='planner'?'#bdc891':'#d4b88a'}/><path d="M96 45v165" stroke="#172838" opacity=".25" strokeWidth="3"/><rect x="110" y="77" width="71" height="2" fill="#eef0da"/><text x="109" y="104" fill={type==='notebook'?'#514233':'#f4f2e5'} fontSize="12" fontWeight="bold" fontFamily="sans-serif">{type==='book'?'DATABASE':type==='planner'?'MAKE':'NOTES &'}</text><text x="109" y="122" fill={type==='notebook'?'#514233':'#f4f2e5'} fontSize="12" fontWeight="bold" fontFamily="sans-serif">{type==='book'?'SYSTEMS':type==='planner'?'IT HAPPEN.':'IDEAS.'}</text><path d="M110 153h55m-55 7h45m-45 7h61" stroke="#eef0da" opacity=".6"/><text x="110" y="197" fill="#f4f2e5" fontSize="6" fontFamily="sans-serif">C A M P U S C A R T</text>{type==='planner'&&<path d="M183 42v174" stroke="#778857" strokeWidth="8"/>}</g>}
    {type==='pens' && <g transform="rotate(26 150 130)">{[0,1,2,3,4].map((n)=><g key={n} transform={`translate(${n*22-42} ${n%2*10})`}><rect x="143" y="55" width="12" height="133" rx="5" fill={n%2?'#4c6b89':'#233d5a'}/><rect x="142" y="42" width="14" height="48" rx="5" fill="#1e3247"/><path d="M155 46v35" stroke="#92a4b7" strokeWidth="3"/><path d="m143 188 6 16 6-16" fill="#c0c7cc"/><path d="m147 199 2 7 2-7" fill="#182638"/></g>)}</g>}
  </svg>;
}
