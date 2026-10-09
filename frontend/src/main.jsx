import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value));
const icons = ['📓', '🖊️', '🎒', '📚', '🗓️', '💧'];

function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({});
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [order, setOrder] = useState(null);
  const [search, setSearch] = useState('');

  async function load() {
    const response = await fetch('/api/products');
    if (!response.ok) throw new Error('Unable to load products. Please try again.');
    const data = await response.json();
    setProducts(data);
  }
  useEffect(() => { load().catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);

  function change(product, delta) {
    setCart(current => {
      const quantity = Math.max(0, Math.min(product.stock, 100, (current[product.id] || 0) + delta));
      const next = { ...current, [product.id]: quantity };
      if (!quantity) delete next[product.id];
      return next;
    });
  }
  const selected = products.filter(p => cart[p.id]);
  const count = Object.values(cart).reduce((a, b) => a + b, 0);
  const total = selected.reduce((sum, p) => sum + Number(p.price) * cart[p.id], 0);

  async function checkout(event) {
    event.preventDefault();
    setError(''); setBusy(true); setOrder(null);
    try {
      const response = await fetch('/api/orders', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_name: name.trim(), items: selected.map(p => ({ product_id: p.id, quantity: cart[p.id] })) })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check your order details.');
      setOrder(data); setCart({}); setName('');
      try { await load(); } catch { setError('Order saved, but stock could not refresh. Reload the page.'); }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <>
    <header><a className="brand" href="/">Campus<span>Cart</span><small>THE STUDENT ESSENTIALS STORE</small></a><a href="#cart" className="bag">Your bag · {count}</a></header>
    <main>
      <section className="hero"><div><span className="eyebrow">A LITTLE PREPARATION. A GREAT SEMESTER.</span><h1>Ready for your<br/><em>next chapter.</em></h1><p>Everyday essentials for campus life.<br/>Thoughtfully picked. Simply priced.</p><a className="button" href="#products">Explore essentials ↗</a></div><div className="hero-art"><span>🎒</span><div className="sticker">PACK LIGHT.<br/>DREAM BIG.</div></div></section>
      {error && <div className="notice error" role="alert">{error}</div>}
      {order && <div className="notice success" role="status"><strong>Order confirmed!</strong> Your order total is {money(order.total)}.<br/><small>Order reference: {order.id}</small></div>}
      <div className="layout"><section id="products"><div className="section-head"><div><span className="eyebrow">YOUR CAMPUS KIT</span><h2>Small things. Big days.</h2></div><input aria-label="Search products" placeholder="Search essentials…" value={search} onChange={e => setSearch(e.target.value)}/></div>
        {loading ? <p>Loading your essentials…</p> : <div className="grid">{products.filter(p => p.name.toLowerCase().includes(search.toLowerCase())).map(p => <article className="product" key={p.id}><div className={'product-art tone-' + p.id}><span aria-hidden="true">{icons[(p.id - 1) % icons.length]}</span><small>{p.stock ? `${p.stock} available` : 'Sold out'}</small></div><h3>{p.name}</h3><p>{p.description}</p><div className="product-bottom"><strong>{money(p.price)}</strong><button aria-label={'Add ' + p.name} disabled={!p.stock || busy || (cart[p.id] || 0) >= Math.min(p.stock, 100)} onClick={() => change(p, 1)}>+ Add</button></div></article>)}</div>}
      </section><aside id="cart"><span className="eyebrow">GOOD CHOICES INSIDE</span><h2>Your bag <span className="count">{count}</span></h2>{!selected.length ? <p className="empty">Your next semester starts here.<br/>Add a few essentials to your bag.</p> : selected.map(p => <div className="cart-line" key={p.id}><div><strong>{p.name}</strong><small>{money(Number(p.price) * cart[p.id])}</small></div><div className="quantity"><button disabled={busy} aria-label={'Remove one ' + p.name} onClick={() => change(p, -1)}>−</button><span>{cart[p.id]}</span><button disabled={busy || cart[p.id] >= Math.min(p.stock, 100)} aria-label={'Add one ' + p.name} onClick={() => change(p, 1)}>+</button></div></div>)}<div className="total"><span>Total</span><strong>{money(total)}</strong></div><form onSubmit={checkout}><label htmlFor="name">Your name</label><input id="name" required maxLength="100" placeholder="e.g. Sathwik" value={name} disabled={busy} onChange={e => setName(e.target.value)}/><button className="checkout" disabled={!selected.length || !name.trim() || busy}>{busy ? 'Placing order…' : 'Place order →'}</button></form><small className="note">College project checkout. No payment is collected.</small></aside></div>
    </main><footer><span>CampusCart © {new Date().getFullYear()}</span><span>Made for campus life.</span></footer>
  </>;
}
createRoot(document.getElementById('root')).render(<App/>);
