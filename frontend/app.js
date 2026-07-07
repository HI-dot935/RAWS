const API = "/api";
let state = {
  cases: [],
  activeCaseId: null,
  activeCase: null,
  activeTool: "username",
};

// ---------------------------------------------------------------- helpers

async function apiGet(path) {
  const r = await fetch(API + path);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function apiPatch(path, body) {
  const r = await fetch(API + path, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
async function apiDelete(path) {
  const r = await fetch(API + path, { method: "DELETE" });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function requireCase() {
  if (!state.activeCaseId) {
    alert("Select or create a case first — every result needs a case to log into.");
    return false;
  }
  return true;
}

// ---------------------------------------------------------------- case management

async function refreshCases(selectId) {
  state.cases = await apiGet("/cases");
  const sel = document.getElementById("caseSelect");
  sel.innerHTML = '<option value="">— No case selected —</option>' +
    state.cases.map(c => `<option value="${c.id}">${escapeHtml(c.name)} (${c.finding_count})</option>`).join("");
  if (selectId) sel.value = selectId;
  if (sel.value) await loadCase(sel.value);
  else { state.activeCaseId = null; state.activeCase = null; renderCaseFile(); }
}

async function loadCase(caseId) {
  state.activeCaseId = caseId;
  state.activeCase = await apiGet(`/cases/${caseId}`);
  renderCaseFile();
}

function renderCaseFile() {
  const title = document.getElementById("caseFileTitle");
  const meta = document.getElementById("caseFileMeta");
  const log = document.getElementById("caseFileLog");
  const badge = document.getElementById("caseStatusBadge");

  if (!state.activeCase) {
    title.textContent = "No active case";
    meta.textContent = "";
    log.innerHTML = '<div class="empty-state">Create or select a case to begin logging findings.</div>';
    badge.textContent = ""; badge.className = "case-status";
    return;
  }
  const c = state.activeCase;
  title.textContent = c.name;
  meta.textContent = `${c.id} · ${c.investigator || "unassigned"} · updated ${new Date(c.updated_at).toLocaleString()}`;
  badge.textContent = c.status;
  badge.className = "case-status " + c.status;

  const findings = c.findings || [];
  if (!findings.length) {
    log.innerHTML = '<div class="empty-state">No findings logged yet. Run a tool on the left — every result lands here automatically.</div>';
  } else {
    log.innerHTML = findings.slice().reverse().map(f => `
      <div class="log-entry" data-finding-id="${f.id}">
        <div class="entry-tool">${escapeHtml(f.tool)}</div>
        <div class="entry-subject">${escapeHtml(f.subject)}</div>
        <div class="entry-summary">${escapeHtml((f.summary || "").slice(0, 160))}</div>
        <div class="entry-meta">
          <span>${new Date(f.created_at).toLocaleString()}</span>
          <button class="del-btn" data-del-id="${f.id}">remove</button>
        </div>
      </div>
    `).join("");
    log.querySelectorAll(".log-entry").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.classList.contains("del-btn")) return;
        const f = findings.find(x => x.id === el.dataset.findingId);
        openFindingModal(f);
      });
    });
    log.querySelectorAll(".del-btn").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await apiDelete(`/findings/${btn.dataset.delId}`);
        await loadCase(state.activeCaseId);
      });
    });
  }

  if (state.activeTool === "notes") renderNotesTool();
}

function openFindingModal(finding) {
  document.getElementById("findingModalTitle").textContent = `${finding.tool} — ${finding.subject}`;
  document.getElementById("findingModalBody").textContent = JSON.stringify(finding.data, null, 2);
  document.getElementById("findingModal").classList.remove("hidden");
}

async function logFindingRefresh(promise) {
  await promise;
  await loadCase(state.activeCaseId);
}

// ---------------------------------------------------------------- tool nav

const TOOL_TITLES = {
  username: ["Username Check", "Search major platforms for a public profile matching a username."],
  email: ["Email Intel", "Validate syntax, check MX records, detect disposable domains, and optionally check HIBP."],
  "domain-ip": ["Domain / IP Recon", "RDAP, DNS, certificate transparency subdomains, geolocation, and optional Shodan."],
  phone: ["Phone Intel (Offline)", "Numbering-plan based analysis — no network calls, fully offline."],
  file: ["File Metadata", "Extract hashes and EXIF/PDF metadata from an uploaded image or PDF."],
  dorks: ["Dork Builder", "Generate clickable search-engine links for a subject."],
  "reverse-image": ["Reverse Image Search", "Generate reverse image search links from an image URL."],
  batch: ["Batch Mode", "Run one tool across up to 25 subjects at once."],
  notes: ["Case Notes", "Free-text investigator notes attached to this case."],
  report: ["Report Export", "Export the full case file as Markdown or PDF."],
};

function setActiveTool(tool) {
  state.activeTool = tool;
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.tool === tool));
  renderTool(tool);
}

function toolHeader(tool) {
  const [title, desc] = TOOL_TITLES[tool];
  return `<div class="tool-header"><h1>${title}</h1><p>${desc}</p></div>`;
}

function renderTool(tool) {
  const panel = document.getElementById("workpanel");
  switch (tool) {
    case "username": return renderUsernameTool(panel);
    case "email": return renderEmailTool(panel);
    case "domain-ip": return renderDomainIpTool(panel);
    case "phone": return renderPhoneTool(panel);
    case "file": return renderFileTool(panel);
    case "dorks": return renderDorksTool(panel);
    case "reverse-image": return renderReverseImageTool(panel);
    case "batch": return renderBatchTool(panel);
    case "notes": return renderNotesTool(panel);
    case "report": return renderReportTool(panel);
  }
}

// ---------------------------------------------------------------- Username

function renderUsernameTool(panel) {
  panel.innerHTML = toolHeader("username") + `
    <div class="form-row">
      <label>Username</label>
      <input type="text" id="usernameInput" placeholder="e.g. johndoe">
      <div class="hint">Checks ~${40} major platforms via public profile URLs. Some sites block automated requests and will show as "unknown" — verify those manually via the link.</div>
    </div>
    <button class="btn btn-accent run-btn" id="runUsername">Run Check</button>
    <div id="usernameResult"></div>
  `;
  document.getElementById("runUsername").onclick = async () => {
    if (!requireCase()) return;
    const username = document.getElementById("usernameInput").value.trim();
    if (!username) return;
    const box = document.getElementById("usernameResult");
    box.innerHTML = '<p class="loading">Checking platforms…</p>';
    try {
      const finding = await apiPost("/tools/username", { case_id: state.activeCaseId, username });
      const data = finding.data;
      box.innerHTML = `
        <div class="result-card">
          <h3>${escapeHtml(username)} <span class="status-pill ok">logged</span></h3>
          <p>${escapeHtml(data.summary || "")}</p>
          <div class="platform-grid">
            ${(data.results || []).map(r => `
              <div class="platform-row">
                <span>${escapeHtml(r.platform)}</span>
                <span>
                  <span class="status-pill ${r.status}">${r.status.replace('_',' ')}</span>
                  <a href="${r.url}" target="_blank" rel="noopener">open</a>
                </span>
              </div>`).join("")}
          </div>
        </div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- Email

function renderEmailTool(panel) {
  panel.innerHTML = toolHeader("email") + `
    <div class="form-row">
      <label>Email address</label>
      <input type="text" id="emailInput" placeholder="name@example.com">
      <div class="hint">HIBP breach lookup only runs if HIBP_API_KEY is configured on the server (optional, requires a paid HIBP subscription key).</div>
    </div>
    <button class="btn btn-accent run-btn" id="runEmail">Run Check</button>
    <div id="emailResult"></div>
  `;
  document.getElementById("runEmail").onclick = async () => {
    if (!requireCase()) return;
    const email = document.getElementById("emailInput").value.trim();
    if (!email) return;
    const box = document.getElementById("emailResult");
    box.innerHTML = '<p class="loading">Checking…</p>';
    try {
      const finding = await apiPost("/tools/email", { case_id: state.activeCaseId, email });
      const d = finding.data;
      box.innerHTML = `
        <div class="result-card">
          <h3>${escapeHtml(email)} <span class="status-pill ${d.valid_syntax ? 'ok' : 'error'}">${d.valid_syntax ? 'valid syntax' : 'invalid'}</span></h3>
          ${d.valid_syntax ? `
          <table class="kv-table">
            <tr><td>Domain</td><td>${escapeHtml(d.domain)}</td></tr>
            <tr><td>MX records</td><td>${d.mx.has_mx ? d.mx.records.map(r => escapeHtml(r.exchange)).join(", ") : (d.mx.error || "none found")}</td></tr>
            <tr><td>Disposable domain</td><td>${d.disposable ? "⚠️ YES — known temporary/disposable provider" : "No"}</td></tr>
            <tr><td>HIBP check</td><td>${
              d.hibp.checked
                ? (d.hibp.breached ? `⚠️ Found in ${d.hibp.breaches.length} breach(es): ${d.hibp.breaches.map(b => escapeHtml(b.Name || b.name || '')).join(", ")}` : "Not found in known breaches")
                : `Skipped — ${escapeHtml(d.hibp.reason || "not configured")}`
            }</td></tr>
          </table>` : `<p>${escapeHtml(d.summary)}</p>`}
        </div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- Domain/IP

function renderDomainIpTool(panel) {
  panel.innerHTML = toolHeader("domain-ip") + `
    <div class="form-row">
      <label>Domain or IP address</label>
      <input type="text" id="domainIpInput" placeholder="example.com or 8.8.8.8">
      <div class="hint">Shodan enrichment for IPs only runs if SHODAN_API_KEY is configured on the server (optional).</div>
    </div>
    <button class="btn btn-accent run-btn" id="runDomainIp">Run Recon</button>
    <div id="domainIpResult"></div>
  `;
  document.getElementById("runDomainIp").onclick = async () => {
    if (!requireCase()) return;
    const subject = document.getElementById("domainIpInput").value.trim();
    if (!subject) return;
    const box = document.getElementById("domainIpResult");
    box.innerHTML = '<p class="loading">Running recon (RDAP, DNS, CT logs, geolocation)…</p>';
    try {
      const finding = await apiPost("/tools/domain-ip", { case_id: state.activeCaseId, subject });
      box.innerHTML = renderDomainIpResult(finding.data);
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

function renderDomainIpResult(d) {
  let rows = `<tr><td>RDAP found</td><td>${d.rdap.found ? "Yes" : "No — " + escapeHtml(d.rdap.error || "")}</td></tr>`;
  if (d.rdap.found) {
    rows += `<tr><td>Handle / name</td><td>${escapeHtml(d.rdap.handle || d.rdap.ldh_name || "")}</td></tr>`;
    rows += `<tr><td>Status</td><td>${(d.rdap.status || []).map(escapeHtml).join(", ")}</td></tr>`;
    rows += `<tr><td>Events</td><td>${(d.rdap.events || []).map(e => `${escapeHtml(e.action)}: ${escapeHtml(e.date)}`).join("<br>")}</td></tr>`;
    if (d.rdap.nameservers && d.rdap.nameservers.length) rows += `<tr><td>Nameservers</td><td>${d.rdap.nameservers.map(escapeHtml).join("<br>")}</td></tr>`;
  }

  if (d.type === "domain") {
    const dns = d.dns || {};
    rows += `<tr><td>A</td><td>${(dns.A || []).map(escapeHtml).join(", ") || "—"}</td></tr>`;
    rows += `<tr><td>AAAA</td><td>${(dns.AAAA || []).map(escapeHtml).join(", ") || "—"}</td></tr>`;
    rows += `<tr><td>MX</td><td>${(dns.MX || []).map(escapeHtml).join("<br>") || "—"}</td></tr>`;
    rows += `<tr><td>NS</td><td>${(dns.NS || []).map(escapeHtml).join("<br>") || "—"}</td></tr>`;
    rows += `<tr><td>TXT</td><td>${(dns.TXT || []).map(escapeHtml).join("<br>") || "—"}</td></tr>`;
    const ct = d.certificate_transparency || {};
    rows += `<tr><td>Subdomains (CT logs)</td><td>${ct.count || 0} found${ct.subdomains && ct.subdomains.length ? "<br>" + ct.subdomains.slice(0, 40).map(escapeHtml).join("<br>") : ""}</td></tr>`;
    if (d.primary_ip_geolocation && d.primary_ip_geolocation.found) {
      const g = d.primary_ip_geolocation;
      rows += `<tr><td>Primary IP geolocation</td><td>${escapeHtml(g.city)}, ${escapeHtml(g.country)} — ${escapeHtml(g.isp || g.org || "")}</td></tr>`;
    }
  } else {
    const g = d.geolocation || {};
    if (g.found) {
      rows += `<tr><td>Location</td><td>${escapeHtml(g.city)}, ${escapeHtml(g.regionName)}, ${escapeHtml(g.country)}</td></tr>`;
      rows += `<tr><td>ISP / Org</td><td>${escapeHtml(g.isp || "")} / ${escapeHtml(g.org || "")}</td></tr>`;
      rows += `<tr><td>ASN</td><td>${escapeHtml(g.as || "")}</td></tr>`;
      rows += `<tr><td>Coordinates</td><td>${g.lat}, ${g.lon}</td></tr>`;
    } else {
      rows += `<tr><td>Geolocation</td><td>${escapeHtml(g.error || "unavailable")}</td></tr>`;
    }
    const sh = d.shodan || {};
    if (sh.checked && sh.found) {
      rows += `<tr><td>Shodan</td><td>Org: ${escapeHtml(sh.org || "")}<br>Open ports: ${(sh.ports || []).join(", ")}<br>Hostnames: ${(sh.hostnames || []).map(escapeHtml).join(", ")}${sh.vulns && sh.vulns.length ? `<br>⚠️ Known vulns: ${sh.vulns.map(escapeHtml).join(", ")}` : ""}</td></tr>`;
    } else {
      rows += `<tr><td>Shodan</td><td>${escapeHtml(sh.reason || "no data")}</td></tr>`;
    }
  }

  return `<div class="result-card"><h3>${escapeHtml(d.subject)} <span class="status-pill ok">logged</span></h3><table class="kv-table">${rows}</table></div>`;
}

// ---------------------------------------------------------------- Phone

function renderPhoneTool(panel) {
  panel.innerHTML = toolHeader("phone") + `
    <div class="form-row">
      <label>Phone number</label>
      <input type="text" id="phoneInput" placeholder="+1 415 555 2671">
      <div class="hint">Include a country code (+1, +44, ...) for best results, or set a default region below.</div>
    </div>
    <div class="form-row">
      <label>Default region (optional, 2-letter code)</label>
      <input type="text" id="phoneRegion" placeholder="US">
    </div>
    <button class="btn btn-accent run-btn" id="runPhone">Analyze</button>
    <div id="phoneResult"></div>
  `;
  document.getElementById("runPhone").onclick = async () => {
    if (!requireCase()) return;
    const phone = document.getElementById("phoneInput").value.trim();
    const region = document.getElementById("phoneRegion").value.trim() || null;
    if (!phone) return;
    const box = document.getElementById("phoneResult");
    box.innerHTML = '<p class="loading">Analyzing…</p>';
    try {
      const finding = await apiPost("/tools/phone", { case_id: state.activeCaseId, phone, region });
      const d = finding.data;
      if (d.error) {
        box.innerHTML = `<div class="result-card"><h3>${escapeHtml(phone)} <span class="status-pill error">invalid</span></h3><p>${escapeHtml(d.error)}</p><p class="hint">${escapeHtml(d.hint || "")}</p></div>`;
      } else {
        box.innerHTML = `<div class="result-card"><h3>${escapeHtml(d.international)} <span class="status-pill ${d.valid ? 'ok' : 'error'}">${d.valid ? 'valid' : 'invalid'}</span></h3>
          <table class="kv-table">
            <tr><td>E.164</td><td>${escapeHtml(d.e164)}</td></tr>
            <tr><td>National format</td><td>${escapeHtml(d.national)}</td></tr>
            <tr><td>Country code</td><td>+${d.country_code}</td></tr>
            <tr><td>Region</td><td>${escapeHtml(d.region_code || "")}</td></tr>
            <tr><td>Number type</td><td>${escapeHtml(d.number_type)}</td></tr>
            <tr><td>Geographic description</td><td>${escapeHtml(d.geographic_description || "—")}</td></tr>
            <tr><td>Carrier hint</td><td>${escapeHtml(d.carrier_hint)}</td></tr>
            <tr><td>Timezones</td><td>${(d.timezones || []).map(escapeHtml).join(", ")}</td></tr>
          </table></div>`;
      }
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- File metadata

function renderFileTool(panel) {
  panel.innerHTML = toolHeader("file") + `
    <div class="dropzone" id="dropzone">
      Drop an image or PDF here, or click to choose a file<br>
      <input type="file" id="fileInput" accept=".jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp,.pdf" style="display:none">
    </div>
    <div id="fileResult"></div>
  `;
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("fileInput");
  dz.onclick = () => input.click();
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("dragover"); };
  dz.ondragleave = () => dz.classList.remove("dragover");
  dz.ondrop = (e) => { e.preventDefault(); dz.classList.remove("dragover"); if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); };
  input.onchange = () => { if (input.files.length) handleFile(input.files[0]); };

  async function handleFile(file) {
    if (!requireCase()) return;
    const box = document.getElementById("fileResult");
    box.innerHTML = '<p class="loading">Extracting metadata…</p>';
    try {
      const fd = new FormData();
      fd.append("case_id", state.activeCaseId);
      fd.append("file", file);
      const r = await fetch(API + "/tools/file", { method: "POST", body: fd });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      const finding = await r.json();
      const d = finding.data;
      let rows = `<tr><td>Size</td><td>${d.size_bytes} bytes</td></tr>
        <tr><td>MD5</td><td>${escapeHtml(d.hashes.md5)}</td></tr>
        <tr><td>SHA1</td><td>${escapeHtml(d.hashes.sha1)}</td></tr>
        <tr><td>SHA256</td><td>${escapeHtml(d.hashes.sha256)}</td></tr>`;
      if (d.file_type === "image") {
        rows += `<tr><td>Format / dimensions</td><td>${escapeHtml(d.format)} — ${escapeHtml(d.dimensions)}</td></tr>`;
        if (d.gps) {
          rows += `<tr><td>GPS</td><td>${d.gps.latitude}, ${d.gps.longitude}${d.gps.map_link ? ` — <a href="${d.gps.map_link}" target="_blank">view on map</a>` : ""}</td></tr>`;
        }
        if (d.exif && Object.keys(d.exif).length) {
          rows += `<tr><td>EXIF</td><td>${Object.entries(d.exif).slice(0, 25).map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(String(v))}`).join("<br>")}</td></tr>`;
        }
      } else if (d.file_type === "pdf") {
        rows += `<tr><td>Pages</td><td>${d.page_count}</td></tr><tr><td>Encrypted</td><td>${d.encrypted}</td></tr>`;
        if (d.metadata) rows += `<tr><td>Document metadata</td><td>${Object.entries(d.metadata).map(([k, v]) => `${escapeHtml(k)}: ${escapeHtml(v)}`).join("<br>")}</td></tr>`;
      } else {
        rows += `<tr><td>Note</td><td>${escapeHtml(d.note || "")}</td></tr>`;
      }
      box.innerHTML = `<div class="result-card"><h3>${escapeHtml(d.filename)} <span class="status-pill ok">logged</span></h3><table class="kv-table">${rows}</table></div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  }
}

// ---------------------------------------------------------------- Dork builder

function renderDorksTool(panel) {
  panel.innerHTML = toolHeader("dorks") + `
    <div class="form-row">
      <label>Subject type</label>
      <select id="dorkType">
        <option value="name">Full name</option>
        <option value="username">Username</option>
        <option value="email">Email</option>
        <option value="domain">Domain</option>
        <option value="phone">Phone number</option>
      </select>
    </div>
    <div class="form-row">
      <label>Subject</label>
      <input type="text" id="dorkSubject" placeholder="Jane Doe / jdoe123 / jane@example.com / example.com">
    </div>
    <button class="btn btn-accent run-btn" id="runDorks">Generate Dorks</button>
    <div id="dorkResult"></div>
  `;
  document.getElementById("runDorks").onclick = async () => {
    if (!requireCase()) return;
    const subject = document.getElementById("dorkSubject").value.trim();
    const subject_type = document.getElementById("dorkType").value;
    if (!subject) return;
    const box = document.getElementById("dorkResult");
    box.innerHTML = '<p class="loading">Generating…</p>';
    try {
      const finding = await apiPost("/tools/dorks", { case_id: state.activeCaseId, subject, subject_type });
      const d = finding.data;
      box.innerHTML = `<div class="result-card"><h3>${escapeHtml(subject)} <span class="status-pill ok">logged</span></h3>
        ${d.groups.map(g => `
          <div class="dork-group">
            ${g.links.map(l => `
              <div class="dork-query">${escapeHtml(l.query)}</div>
              <div class="dork-links">${l.engines.map(e => `<a href="${e.url}" target="_blank" rel="noopener">${escapeHtml(e.engine)}</a>`).join("")}</div>
            `).join("")}
          </div>`).join("")}
      </div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

function renderReverseImageTool(panel) {
  panel.innerHTML = toolHeader("reverse-image") + `
    <div class="form-row">
      <label>Image URL</label>
      <input type="text" id="imgUrlInput" placeholder="https://example.com/photo.jpg">
      <div class="hint">Paste a direct link to a publicly hosted image. Google Images requires manual upload — a link to the tool is provided.</div>
    </div>
    <button class="btn btn-accent run-btn" id="runReverseImage">Generate Links</button>
    <div id="reverseImageResult"></div>
  `;
  document.getElementById("runReverseImage").onclick = async () => {
    if (!requireCase()) return;
    const image_url = document.getElementById("imgUrlInput").value.trim();
    if (!image_url) return;
    const box = document.getElementById("reverseImageResult");
    box.innerHTML = '<p class="loading">Generating…</p>';
    try {
      const finding = await apiPost("/tools/reverse-image", { case_id: state.activeCaseId, image_url });
      const d = finding.data;
      box.innerHTML = `<div class="result-card"><h3>Reverse image links <span class="status-pill ok">logged</span></h3>
        <div class="dork-links">${d.links.map(l => `<a href="${l.url}" target="_blank" rel="noopener">${escapeHtml(l.engine)}</a>`).join("")}</div>
      </div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- Batch mode

function renderBatchTool(panel) {
  panel.innerHTML = toolHeader("batch") + `
    <div class="form-row">
      <label>Tool</label>
      <select id="batchTool">
        <option value="username">Username Check</option>
        <option value="email">Email Intel</option>
        <option value="domain-ip">Domain / IP Recon</option>
        <option value="phone">Phone Intel</option>
      </select>
    </div>
    <div class="form-row">
      <label>Subjects (one per line, up to 25)</label>
      <textarea id="batchSubjects" class="batch-textarea" placeholder="one subject per line"></textarea>
    </div>
    <div class="form-row" id="batchRegionRow" style="display:none">
      <label>Default region for phone numbers (optional)</label>
      <input type="text" id="batchRegion" placeholder="US">
    </div>
    <button class="btn btn-accent run-btn" id="runBatch">Run Batch</button>
    <div id="batchResult"></div>
  `;
  document.getElementById("batchTool").onchange = (e) => {
    document.getElementById("batchRegionRow").style.display = e.target.value === "phone" ? "block" : "none";
  };
  document.getElementById("runBatch").onclick = async () => {
    if (!requireCase()) return;
    const tool = document.getElementById("batchTool").value;
    const subjects = document.getElementById("batchSubjects").value.split("\n").map(s => s.trim()).filter(Boolean);
    const region = document.getElementById("batchRegion").value.trim() || null;
    if (!subjects.length) return;
    if (subjects.length > 25) { alert("Batch mode supports at most 25 subjects."); return; }
    const box = document.getElementById("batchResult");
    box.innerHTML = `<p class="loading">Running ${tool} on ${subjects.length} subject(s)…</p>`;
    try {
      const res = await apiPost("/tools/batch", { case_id: state.activeCaseId, tool, subjects, region });
      box.innerHTML = `<div class="result-card"><h3>Batch complete <span class="status-pill ok">${res.count} logged</span></h3>
        <table class="kv-table">${res.results.map(r => `<tr><td>${escapeHtml(r.subject)}</td><td>${escapeHtml(r.summary || "")}</td></tr>`).join("")}</table>
      </div>`;
      await loadCase(state.activeCaseId);
    } catch (e) { box.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- Notes

function renderNotesTool(panelMaybe) {
  const panel = panelMaybe || document.getElementById("workpanel");
  if (state.activeTool !== "notes") return;
  const notes = (state.activeCase && state.activeCase.notes) || [];
  panel.innerHTML = toolHeader("notes") + `
    <div class="form-row">
      <label>Add a note</label>
      <textarea id="noteInput" rows="3" placeholder="Free-text observation, hypothesis, or next step..."></textarea>
    </div>
    <button class="btn btn-accent run-btn" id="addNoteBtn">Add Note</button>
    <div class="notes-list">
      ${notes.slice().reverse().map(n => `<div class="note-item"><span class="note-time">${new Date(n.created_at).toLocaleString()}</span>${escapeHtml(n.note)}</div>`).join("") || '<p class="hint">No notes yet.</p>'}
    </div>
  `;
  document.getElementById("addNoteBtn").onclick = async () => {
    if (!requireCase()) return;
    const note = document.getElementById("noteInput").value.trim();
    if (!note) return;
    await apiPost(`/cases/${state.activeCaseId}/notes`, { note });
    await loadCase(state.activeCaseId);
    renderNotesTool(panel);
  };
}

// ---------------------------------------------------------------- Report

function renderReportTool(panel) {
  panel.innerHTML = toolHeader("report") + `
    <p>Export everything logged in this case — findings, notes, and metadata — as a formatted case report.</p>
    <div class="report-actions">
      <button class="btn btn-accent" id="exportMd">Export Markdown</button>
      <button class="btn btn-accent" id="exportPdf">Export PDF</button>
    </div>
    <div id="reportStatus" style="margin-top:12px;"></div>
  `;
  document.getElementById("exportMd").onclick = () => {
    if (!requireCase()) return;
    window.open(`${API}/cases/${state.activeCaseId}/report.md`, "_blank");
  };
  document.getElementById("exportPdf").onclick = async () => {
    if (!requireCase()) return;
    const status = document.getElementById("reportStatus");
    status.innerHTML = '<p class="loading">Rendering PDF…</p>';
    try {
      const r = await fetch(`${API}/cases/${state.activeCaseId}/report.pdf`);
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `case_${state.activeCaseId}.pdf`; a.click();
      status.innerHTML = "";
    } catch (e) { status.innerHTML = `<p class="loading">Error: ${escapeHtml(e.message)}</p>`; }
  };
}

// ---------------------------------------------------------------- wiring

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => setActiveTool(btn.dataset.tool));
});

document.getElementById("caseSelect").addEventListener("change", async (e) => {
  if (e.target.value) await loadCase(e.target.value);
  else { state.activeCaseId = null; state.activeCase = null; renderCaseFile(); }
});

document.getElementById("newCaseBtn").addEventListener("click", () => {
  document.getElementById("newCaseModal").classList.remove("hidden");
});
document.getElementById("cancelNewCase").addEventListener("click", () => {
  document.getElementById("newCaseModal").classList.add("hidden");
});
document.getElementById("confirmNewCase").addEventListener("click", async () => {
  const name = document.getElementById("newCaseName").value.trim();
  if (!name) { alert("Case name is required."); return; }
  const investigator = document.getElementById("newCaseInvestigator").value.trim();
  const description = document.getElementById("newCaseDescription").value.trim();
  const created = await apiPost("/cases", { name, investigator, description });
  document.getElementById("newCaseModal").classList.add("hidden");
  document.getElementById("newCaseName").value = "";
  document.getElementById("newCaseInvestigator").value = "";
  document.getElementById("newCaseDescription").value = "";
  await refreshCases(created.id);
});

document.getElementById("closeCaseBtn").addEventListener("click", async () => {
  if (!requireCase()) return;
  const next = state.activeCase.status === "open" ? "closed" : "open";
  await apiPatch(`/cases/${state.activeCaseId}/status`, { status: next });
  await loadCase(state.activeCaseId);
});

document.getElementById("closeFindingModal").addEventListener("click", () => {
  document.getElementById("findingModal").classList.add("hidden");
});

// initial load
refreshCases();
setActiveTool("username");
