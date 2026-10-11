import React,{createContext,useContext,useEffect,useState} from 'react';
const Context=createContext(null);
export function useSession(){return useContext(Context);}
export async function api(path,options={}){
 const headers={'Content-Type':'application/json','X-CSRF-Token':sessionStorage.getItem('campuscart:csrf')||'',...options.headers};
 const response=await fetch('/api'+path,{...options,headers,body:options.body?JSON.stringify(options.body):undefined});
 const data=await response.json();
 if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:'Please check the entered values.');error.status=response.status;throw error;}
 return data;
}
export function SessionProvider({children}){
 const [brand,setBrand]=useState({name:'CampusCart University',initials:'CU',tagline:'Your campus. Your essentials.'}),[unread,setUnread]=useState(0);
 const [user,setUser]=useState(null),[ready,setReady]=useState(false),[route,setRoute]=useState(location.hash.startsWith('#/')?location.hash.slice(2):'');
 function navigate(path=''){location.hash='/'+path;window.scrollTo(0,0);}
 function authenticate(data){setUser(data.user);sessionStorage.setItem('campuscart:csrf',data.csrf);}
 useEffect(()=>{const change=()=>{if(location.hash.startsWith('#/')){setRoute(location.hash.slice(2));window.scrollTo(0,0);}};window.addEventListener('hashchange',change);api('/auth/me').then(authenticate).catch(()=>{}).finally(()=>setReady(true));return()=>window.removeEventListener('hashchange',change);},[]);
 async function refreshNotifications(){try{const data=await api('/notifications');setUnread(data.unread);}catch{}}
 useEffect(()=>{api('/brand').then(setBrand).catch(()=>{});},[]);
 useEffect(()=>{if(!user){setUnread(0);return;}refreshNotifications();const timer=setInterval(refreshNotifications,30000);return()=>clearInterval(timer);},[user?.id]);
 async function logout(){await api('/auth/logout',{method:'POST'});setUser(null);sessionStorage.removeItem('campuscart:csrf');navigate('');}
 return <Context.Provider value={{brand,setBrand,unread,refreshNotifications,user,setUser,ready,route,navigate,authenticate,logout,requestLogin:()=>navigate('account')}}>{children}</Context.Provider>;
}
