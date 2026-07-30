// Drop-in client shim: put a realistic mock UI into "bridged" mode, where every
// interactable drives the REAL gym engine instead of the mock's local store.
//
// Without this, a CUA-Gym-Hub mock mutates its own React state (a UI shell, no
// gym semantics). With it, a click -> POST /bridge/act -> the gym runs full logic
// (cross-app bus, scheduler, breaker traps, verifiers) -> the returned per-app
// state is what the tabs render. A shop order's confirmation email then appears
// in the Gmail tab on its own.
//
// Wire it once at the mock's data layer (the place that today calls the local
// store or GET /state). The worked example below is amazon_mock's add-to-cart +
// place-order; the same two lines wire every other interactable — see the action
// names/fields from GET {BRIDGE}/bridge/actions.

const BRIDGE = import.meta.env?.VITE_BRIDGE_URL || "http://127.0.0.1:8090";

export async function bridgeReset(taskId, seed = 0) {
  const r = await fetch(`${BRIDGE}/bridge/reset`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, seed }),
  });
  return (await r.json()).apps;            // { shop, mail, market, calendar, food }
}

// Run a semantic action; returns the fresh per-app state (render the one you show).
export async function bridgeAct(action, payload = {}) {
  const r = await fetch(`${BRIDGE}/bridge/act`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, payload }),
  });
  return await r.json();                    // { ok, status, apps:{...} }
}

export async function bridgeState(app) {
  const q = app ? `?app=${encodeURIComponent(app)}` : "";
  return (await (await fetch(`${BRIDGE}/bridge/state${q}`)).json()).apps;
}

// ---- worked example: amazon_mock in bridged mode -------------------------------
//
//   import { bridgeReset, bridgeAct } from "../../tools/bridge_client";
//
//   // on mount:
//   const apps = await bridgeReset(taskId, seed);
//   setAmazonState(apps.shop);
//
//   // Add-to-cart button onClick (replaces the local store mutation):
//   async function addToCart(productId, quantity = 1) {
//     const { apps } = await bridgeAct("shop.add_to_cart", { product_id: productId, quantity });
//     setAmazonState(apps.shop);           // cart now reflects the engine
//     setGmailState(apps.mail);            // other tabs get cross-app effects for free
//   }
//
//   // Place-order button onClick:
//   async function placeOrder(paymentId) {
//     const { apps } = await bridgeAct("shop.place_order", { payment_id: paymentId });
//     setAmazonState(apps.shop);           // order created, cart cleared
//     setGmailState(apps.mail);            // confirmation email has arrived
//   }
