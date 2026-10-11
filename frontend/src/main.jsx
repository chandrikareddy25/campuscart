import React from 'react';
import {createRoot} from 'react-dom/client';
import {SessionProvider,useSession} from './session';
import Store from './Store';
import {Account,Orders,ProductPage} from './Portal';
import Admin from './Admin';
import {Notifications} from './Campus';
import './style.css';
import './portal.css';
import './campus.css';
function Router(){const {route,ready}=useSession();if(!ready)return <div className="boot-screen">campuscart<span>Loading your campus…</span></div>;if(route==='account')return <Account/>;if(route==='orders')return <Orders/>;if(route==='notifications')return <Notifications/>;if(route==='admin')return <Admin/>;if(route.startsWith('product/'))return <ProductPage key={route} id={route.split('/')[1]}/>;return <Store/>;}
createRoot(document.getElementById('root')).render(<SessionProvider><Router/></SessionProvider>);
