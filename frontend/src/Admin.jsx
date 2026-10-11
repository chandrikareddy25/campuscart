import React, { useEffect, useState } from "react";
import { api, useSession } from "./session";
import { Page } from "./Portal";
import { money, artOf } from "./catalog";
import { Icon, ProductArt } from "./Art";
import { OrderBilling, BillingSummary } from "./Billing";
import { CollectionDesk, CampusSettings, slotLabel } from "./Campus";
const categories = [
  "Books",
  "Stationery",
  "Bags",
  "Accessories",
  "Tech",
  "Merchandise",
  "Lab essentials",
];
const stages = ["placed", "preparing", "ready", "collected"];
function Bars({ data, value, label }) {
  const max = Math.max(1, ...data.map((d) => Number(d[value])));
  return (
    <div className="bar-chart">
      {data.map((d, i) => (
        <div className="bar-column" key={i}>
          <strong>{value === "revenue" ? money(d[value]) : d[value]}</strong>
          <div className="bar-track">
            <span
              style={{
                height: Math.max(2, (Number(d[value]) / max) * 100) + "%",
              }}
            />
          </div>
          <small>{String(d[label]).slice(-5)}</small>
        </div>
      ))}
    </div>
  );
}
export default function Admin() {
  const { user, navigate } = useSession();
  const [tab, setTab] = useState("overview"),
    [products, setProducts] = useState([]),
    [orders, setOrders] = useState([]),
    [analytics, setAnalytics] = useState(null),
    [error, setError] = useState(""),
    [editor, setEditor] = useState(null),
    [filter, setFilter] = useState("all"),
    [search, setSearch] = useState(""),
    [busy, setBusy] = useState(false);
  async function load() {
    try {
      const [p, o, a] = await Promise.all([
        api("/admin/products"),
        api("/admin/orders"),
        api("/admin/analytics"),
      ]);
      setProducts(p);
      setOrders(o);
      setAnalytics(a);
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    if (user?.role === "admin") load();
  }, [user?.id]);
  async function save(e) {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    try {
      let specs = {};
      for (const line of form.specifications.split("\n").filter(Boolean)) {
        const index = line.indexOf(":");
        if (index < 1) throw new Error("Use Key: Value for each specification");
        specs[line.slice(0, index).trim()] = line.slice(index + 1).trim();
      }
      const body = {
        ...form,
        price: Number(form.price),
        stock: Number(form.stock),
        images: form.images
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        specifications: specs,
        featured: form.featured === "on",
        active: form.active === "on",
      };
      await api("/admin/products" + (editor.id ? "/" + editor.id : ""), {
        method: editor.id ? "PUT" : "POST",
        body,
      });
      setEditor(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (user?.role !== "admin")
    return (
      <Page
        title="Administrator access"
        subtitle="This area is restricted to authorized administrators."
      >
        <button className="button navy" onClick={() => navigate("account")}>
          Sign in with an admin account
        </button>
      </Page>
    );
  return (
    <Page
      title="Campus operations."
      subtitle="Manage the products, orders, and inventory that keep campus life moving."
    >
      <div className="admin-layout">
        <aside className="admin-sidebar">
          {["overview", "products", "orders", "collection", "campus"].map(
            (t) => (
              <button
                className={tab === t ? "selected" : ""}
                key={t}
                onClick={() => setTab(t)}
              >
                <Icon
                  name={
                    t === "overview"
                      ? "cube"
                      : t === "products"
                        ? "bag"
                        : "book"
                  }
                />
                {t}
              </button>
            ),
          )}
          <button onClick={load}>Refresh data</button>
          <small>
            Signed in as
            <br />
            {user.email}
          </small>
        </aside>
        <section className="admin-content">
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {tab === "overview" && analytics && (
            <>
              <BillingSummary />
              <div className="stat-grid">
                {[
                  ["Order value", money(analytics.summary.revenue)],
                  ["Orders", analytics.summary.orders],
                  ["Students", analytics.students],
                  ["Low-stock products", analytics.products.low_stock],
                ].map(([k, v]) => (
                  <div className="stat-card" key={k}>
                    <span>{k}</span>
                    <strong>{v}</strong>
                  </div>
                ))}
              </div>
              <div className="form-card">
                <h2>Orders · last 14 days</h2>
                <Bars data={analytics.daily} value="orders" label="day" />
              </div>
              <div className="admin-two">
                <div className="form-card">
                  <h2>Category sales</h2>
                  {analytics.categories.length ? (
                    analytics.categories.map((c) => (
                      <div className="sales-row" key={c.category}>
                        <span>
                          {c.category}
                          <small>{c.units} units</small>
                        </span>
                        <strong>{money(c.revenue)}</strong>
                      </div>
                    ))
                  ) : (
                    <p className="muted">No order items yet.</p>
                  )}
                  <small>
                    Order values; recorded payments are shown separately.
                  </small>
                </div>
                <div className="form-card">
                  <h2>Inventory attention</h2>
                  {analytics.low_stock.length ? (
                    analytics.low_stock.map((p) => (
                      <div className="sales-row" key={p.id}>
                        <span>{p.name}</span>
                        <strong>{p.stock} left</strong>
                      </div>
                    ))
                  ) : (
                    <p className="muted">
                      All active products have more than five units.
                    </p>
                  )}
                  <p className="muted">
                    {analytics.summary.new_orders} orders awaiting preparation ·{" "}
                    {analytics.summary.ready_orders} ready for collection
                  </p>
                </div>
              </div>
            </>
          )}
          {tab === "collection" && <CollectionDesk onCollected={load} />}
          {tab === "campus" && <CampusSettings />}
          {tab === "products" && (
            <>
              <div className="admin-toolbar">
                <h2>Product catalog</h2>
                <button
                  className="button navy"
                  onClick={() => {
                    setError("");
                    setEditor({
                      name: "",
                      description: "",
                      price: 0,
                      stock: 0,
                      category: "Stationery",
                      images: [],
                      specifications: {},
                      active: true,
                      featured: false,
                    });
                  }}
                >
                  Add product +
                </button>
              </div>
              <input
                className="admin-search"
                aria-label="Search admin products"
                placeholder="Search product name…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Category</th>
                      <th>Price</th>
                      <th>Stock</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {products
                      .filter((p) =>
                        p.name.toLowerCase().includes(search.toLowerCase()),
                      )
                      .map((p) => (
                        <tr key={p.id}>
                          <td>
                            <div className="table-product">
                              <ProductArt type={artOf(p)} images={p.images} />
                              <span>{p.name}</span>
                            </div>
                          </td>
                          <td>{p.category}</td>
                          <td>{money(p.price)}</td>
                          <td className={p.stock <= 5 ? "low-stock" : ""}>
                            {p.stock}
                          </td>
                          <td>{p.active ? "Active" : "Archived"}</td>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => {
                                setEditor(p);
                                setError("");
                              }}
                            >
                              Edit
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {tab === "orders" && (
            <>
              <div className="admin-toolbar">
                <h2>Order processing</h2>
                <select
                  aria-label="Filter admin orders"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">All statuses</option>
                  {[...stages, "cancelled"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              {orders
                .filter((o) => filter === "all" || o.status === filter)
                .map((o) => (
                  <article className="admin-order" key={o.id}>
                    <div className="order-heading">
                      <div>
                        <strong>{o.customer_name}</strong>
                        <p>
                          {o.id.slice(0, 8)} ·{" "}
                          {new Date(o.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <span className={"status " + o.status}>{o.status}</span>
                      <strong>{money(o.total)}</strong>
                    </div>
                    <p>
                      {o.pickup_name || "Legacy order — no pickup selected"}
                    </p>
                    {o.pickup_slot && <p>{slotLabel(o.pickup_slot)}</p>}
                    <OrderBilling order={o} admin onPaid={load} />
                    <ul>
                      {o.items.map((i) => (
                        <li key={i.id}>
                          {i.product_name} × {i.quantity}
                        </li>
                      ))}
                    </ul>
                    {o.notes && <p>Notes: {o.notes}</p>}
                    {o.status === "ready" && o.pickup_slot_id ? (
                      <button
                        className="button navy"
                        onClick={() => setTab("collection")}
                      >
                        Verify QR at collection desk →
                      </button>
                    ) : (
                      o.status !== "collected" &&
                      o.status !== "cancelled" && (
                        <button
                          className="button navy"
                          onClick={async () => {
                            setBusy(true);
                            try {
                              await api("/admin/orders/" + o.id + "/status", {
                                method: "PATCH",
                                body: {
                                  status: stages[stages.indexOf(o.status) + 1],
                                },
                              });
                              await load();
                            } catch (e) {
                              setError(e.message);
                            } finally {
                              setBusy(false);
                            }
                          }}
                          disabled={busy}
                        >
                          Mark{" "}
                          {stages[stages.indexOf(o.status) + 1] === "ready"
                            ? "ready for pickup"
                            : stages[stages.indexOf(o.status) + 1]}{" "}
                          →
                        </button>
                      )
                    )}
                  </article>
                ))}
            </>
          )}
        </section>
      </div>
      {editor && (
        <div className="editor-overlay">
          <form className="product-editor form-card" onSubmit={save}>
            <div className="admin-toolbar">
              <h2>{editor.id ? "Edit product" : "New product"}</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setEditor(null)}
                aria-label="Close product editor"
              >
                <Icon name="close" />
              </button>
            </div>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <label>
              Product name
              <input
                name="name"
                defaultValue={editor.name}
                required
                maxLength={150}
              />
            </label>
            <label>
              Description
              <textarea
                name="description"
                defaultValue={editor.description}
                required
                maxLength={2000}
              />
            </label>
            <div className="admin-two">
              <label>
                Price (INR)
                <input
                  name="price"
                  type="number"
                  step=".01"
                  min="0"
                  max="99999999"
                  defaultValue={editor.price}
                  required
                />
              </label>
              <label>
                Stock
                <input
                  name="stock"
                  type="number"
                  min="0"
                  max="100000"
                  defaultValue={editor.stock}
                  required
                />
              </label>
            </div>
            <label>
              Category
              <select name="category" defaultValue={editor.category}>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label>
              Product image URLs (HTTPS, one per line)
              <textarea
                name="images"
                defaultValue={(editor.images || []).join("\n")}
                placeholder="https://…"
              />
            </label>
            <label>
              Specifications (Key: Value, one per line)
              <textarea
                name="specifications"
                defaultValue={Object.entries(editor.specifications || {})
                  .map(([k, v]) => k + ": " + v)
                  .join("\n")}
              />
            </label>
            <div className="check-fields">
              <label>
                <input
                  type="checkbox"
                  name="active"
                  defaultChecked={editor.active}
                />{" "}
                Active in store
              </label>
              <label>
                <input
                  type="checkbox"
                  name="featured"
                  defaultChecked={editor.featured}
                />{" "}
                Featured
              </label>
            </div>
            <button className="button navy full" disabled={busy}>
              {busy ? "Saving…" : "Save product"}
            </button>
            <small>
              Archive a product to remove it from the catalog while preserving
              order history.
            </small>
          </form>
        </div>
      )}
    </Page>
  );
}
