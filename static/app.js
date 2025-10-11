let originPlace = null;
let destinationPlace = null;

function initAutocomplete() {
  const sw = new google.maps.LatLng(31.56, -106.68);
  const ne = new google.maps.LatLng(31.92, -106.26);
  const bounds = new google.maps.LatLngBounds(sw, ne);

  const opts = {
    bounds,
    strictBounds: true,
    fields: ["place_id", "geometry", "formatted_address", "name"],
    types: ["address"],
  };

  const originInput = document.getElementById("origin");
  const destInput   = document.getElementById("destination");

  const originAC = new google.maps.places.Autocomplete(originInput, opts);
  const destAC   = new google.maps.places.Autocomplete(destInput, opts);

  originAC.addListener("place_changed", () => {
    const p = originAC.getPlace();
    originPlace = p?.geometry?.location
      ? { lat: p.geometry.location.lat(), lng: p.geometry.location.lng() }
      : null;
  });

  destAC.addListener("place_changed", () => {
    const p = destAC.getPlace();
    destinationPlace = p?.geometry?.location
      ? { lat: p.geometry.location.lat(), lng: p.geometry.location.lng() }
      : null;
  });

  document.getElementById("go").addEventListener("click", onCalculate);
}
window.initAutocomplete = initAutocomplete;

async function onCalculate() {
  const msg = document.getElementById("msg");
  const results = document.getElementById("results");
  const winner = document.getElementById("winner");
  const cards = document.getElementById("cards");

  msg.textContent = "";
  results.classList.add("hidden");
  cards.innerHTML = "";

  if (!originPlace || !destinationPlace) {
    msg.textContent = "Pick both addresses from the dropdown.";
    return;
  }

  const mode = document.getElementById("mode").value;

  try {
    const res = await fetch("/api/best-crossing", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        origin: { lat: originPlace.lat, lng: originPlace.lng },
        destination: { lat: destinationPlace.lat, lng: destinationPlace.lng },
        mode
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Server error");

    winner.textContent = `Fastest: ${data.bridge} (${fmtS(data.total_s)})`;

    const items = Object.entries(data.breakdown)
      .sort((a, b) => a[1].total_s - b[1].total_s);

    for (const [name, d] of items) {
      const el = document.createElement("div");
      el.className = "card";
      el.innerHTML = `
        <h3>${name}</h3>
        <div class="row"><span>Total</span><b>${fmtS(d.total_s)}</b></div>
        <div class="row"><span>Wait</span><b>${d.wait_min} min</b></div>
        <div class="row"><span>To bridge</span><b>${fmtS(d.to_bridge_s)}</b></div>
        <div class="row"><span>From bridge</span><b>${fmtS(d.from_bridge_s)}</b></div>
      `;
      cards.appendChild(el);
    }

    results.classList.remove("hidden");
  } catch (e) {
    msg.textContent = e.message;
  }
}

function fmtS(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  let m = Math.floor(s / 60);
  const sec = s % 60;
  const h = Math.floor(m / 60);
  m = m % 60;
  return h ? `${h}h ${m}m` : `${m}m ${sec}s`;
}
