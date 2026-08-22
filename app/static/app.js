const $ = (sel) => document.querySelector(sel);
const toast = (msg) => {
  const el = $("#toast");
  el.hidden = false;
  el.textContent = msg;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 3200);
};

function showSentModal(note) {
  $("#sent-summary").textContent = [
    `To: ${note.to}`,
    `Subject: ${note.subject}`,
    note.resume ? `Resume attached: ${note.resume}` : "No resume was attached. Upload one on Profile or this page.",
  ].join(" · ");
  $("#sent-modal").hidden = false;
}

$("#sent-close").onclick = () => { $("#sent-modal").hidden = true; };
$("#sent-modal").addEventListener("click", (e) => {
  if (e.target.id === "sent-modal") $("#sent-modal").hidden = true;
});

function letterHtml(subject, body, extras = {}) {
  const skills = (extras.matched_skills || []).map((s) => `<span class="role-tag">${escapeHtml(s)}</span>`).join("");
  const resume = extras.resume_name
    ? `<p class="attach-note">Resume will be attached: ${escapeHtml(extras.resume_name)}</p>`
    : `<p class="hint">Upload a resume so it goes out with the email.</p>`;
  return `
    <p class="kicker">Email preview</p>
    <p class="letter-meta">${escapeHtml(extras.to ? `To ${extras.to}` : "Add a recruiter email before sending")}</p>
    ${skills ? `<div class="skill-row">${skills}</div>` : ""}
    <div class="letter-card"><strong>${escapeHtml(subject || "Subject will appear here")}</strong>${escapeHtml(body || "")}</div>
    ${resume}
  `;
}

const state = { jobs: [], currentId: null };

async function api(path, options = {}) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

function formBody(obj) {
  const body = new FormData();
  Object.entries(obj).forEach(([k, v]) => body.append(k, v ?? ""));
  return body;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $(`#view-${name}`).classList.add("active");
  const titles = {
    inbox: ["Inbox", "Cloud, DevOps, and admin roles"],
    import: ["Import", "Paste a matching LinkedIn job"],
    watch: ["Watchers", "Public board alerts"],
    profile: ["Profile", "Resume and pitch"],
  };
  $("#view-kicker").textContent = titles[name][0];
  $("#view-title").textContent = titles[name][1];
}

async function loadStatus() {
  const s = await api("/api/status");
  $("#stats").innerHTML = [
    ["Target jobs", s.jobs],
    ["With email", s.with_email],
    ["Drafts", s.drafts],
    ["Sent", s.sent],
  ].map(([label, n]) => `<div class="stat"><b>${n}</b><span>${label}</span></div>`).join("");
  const pill = $("#mail-status");
  pill.textContent = s.mail_ready ? "Gmail ready" : "Add SMTP_APP_PASSWORD in .env";
  pill.className = `mail-pill ${s.mail_ready ? "ready" : "missing"}`;
}

async function loadJobs() {
  state.jobs = await api("/api/jobs");
  renderJobs($("#job-filter").value);
}

function renderJobs(filter = "") {
  const q = filter.toLowerCase();
  const items = state.jobs.filter((j) =>
    `${j.title} ${j.company} ${j.recruiter_email}`.toLowerCase().includes(q)
  );
  const list = $("#job-list");
  if (!items.length) {
    list.innerHTML = `<div class="empty">No matching Cloud / DevOps / admin jobs yet. Click a role above to search LinkedIn, or load public-board matches.</div>`;
    return;
  }
  list.innerHTML = items.map((j) => `
    <button class="job-item ${j.id === state.currentId ? "active" : ""}" data-id="${j.id}">
      <h3>${escapeHtml(j.title)}</h3>
      <p>${escapeHtml(j.company || "Unknown company")}</p>
      ${(j.roles || []).map((role) => `<span class="role-tag">${escapeHtml(role)}</span>`).join("")}
      <span class="badge ${j.status}">${j.status}${j.recruiter_email ? " · email found" : " · no email"}</span>
    </button>
  `).join("");
}

async function openJob(id) {
  state.currentId = id;
  renderJobs($("#job-filter").value);
  const data = await api(`/api/jobs/${id}`);
  const job = data.job;
  const draft = data.drafts[0];
  $("#job-detail").innerHTML = `
    <div class="detail">
      <h2>${escapeHtml(job.title)}</h2>
      <p class="meta">${escapeHtml(job.company || "Company not listed")} · ${escapeHtml(job.location || "Location not listed")}</p>
      <p>${(job.roles || []).map((role) => `<span class="role-tag">${escapeHtml(role)}</span>`).join("")}</p>
      ${job.url ? `<p class="meta"><a href="${escapeAttr(job.url)}" target="_blank" rel="noreferrer">Open posting</a></p>` : ""}
      <div class="letter-wrap">
        ${letterHtml(draft?.subject || "", draft?.body || "", {
          to: job.recruiter_email,
          resume_name: data.resume_name,
        })}
      </div>
      <label>Recruiter name</label>
      <input id="rec-name" value="${escapeAttr(job.recruiter_name)}" />
      <label>Recruiter email</label>
      <input id="rec-email" value="${escapeAttr(job.recruiter_email)}" placeholder="name@company.com" />
      ${data.emails.length ? `<p class="hint">Found: ${data.emails.map(escapeHtml).join(", ")}</p>` : `<p class="hint">No email in the posting. Add one by hand if you have it.</p>`}
      <div class="detail-actions">
        <button class="ghost" id="save-contact">Save contact</button>
        <button class="primary" id="make-draft">Rewrite professional draft</button>
        <button class="ghost danger" id="delete-job">Delete</button>
      </div>
      <label>Subject</label>
      <input id="draft-subject" value="${escapeAttr(draft?.subject || "")}" />
      <label>Email body</label>
      <textarea id="draft-body">${escapeHtml(draft?.body || "")}</textarea>
      <label>Resume attachment</label>
      <div class="resume-box">
        <input id="send-resume" type="file" accept=".pdf,.doc,.docx" />
        <p class="hint">${data.has_resume ? `Current file: ${escapeHtml(data.resume_name)}` : "No resume loaded. Choose a PDF before sending."}</p>
      </div>
      <div class="detail-actions">
        <button class="primary" id="send-draft" ${draft ? "" : "disabled"}>Send application</button>
        ${draft ? `<span class="hint">Draft #${draft.id} · ${draft.status}${draft.error ? " · " + escapeHtml(draft.error) : ""}</span>` : ""}
      </div>
    </div>
  `;
  $("#save-contact").onclick = async () => {
    await api(`/api/jobs/${id}`, {
      method: "PATCH",
      body: formBody({
        recruiter_email: $("#rec-email").value,
        recruiter_name: $("#rec-name").value,
      }),
    });
    toast("Contact saved");
    loadJobs();
  };
  $("#make-draft").onclick = async () => {
    await api(`/api/jobs/${id}`, {
      method: "PATCH",
      body: formBody({
        recruiter_email: $("#rec-email").value,
        recruiter_name: $("#rec-name").value,
      }),
    });
    await api(`/api/jobs/${id}/draft`, { method: "POST" });
    toast("Draft written from your profile");
    openJob(id);
    loadStatus();
    loadJobs();
  };
  $("#delete-job").onclick = async () => {
    await api(`/api/jobs/${id}`, { method: "DELETE" });
    state.currentId = null;
    $("#job-detail").innerHTML = `<div class="empty">Select a job to review the recruiter email and draft.</div>`;
    loadJobs();
    loadStatus();
  };
  $("#send-draft").onclick = async () => {
    if (!draft) return;
    await api(`/api/jobs/${id}`, {
      method: "PATCH",
      body: formBody({
        recruiter_email: $("#rec-email").value,
        recruiter_name: $("#rec-name").value,
      }),
    });
    await api(`/api/drafts/${draft.id}`, {
      method: "PATCH",
      body: formBody({
        subject: $("#draft-subject").value,
        body: $("#draft-body").value,
      }),
    });
    try {
      const body = new FormData();
      const resumeFile = $("#send-resume")?.files?.[0];
      if (resumeFile) body.append("resume", resumeFile);
      const sent = await api(`/api/drafts/${draft.id}/send`, { method: "POST", body });
      showSentModal(sent.notification || {
        to: $("#rec-email").value,
        subject: $("#draft-subject").value,
        resume: sent.resume_name || "",
      });
    } catch (err) {
      toast(err.message);
    }
    openJob(id);
    loadJobs();
    loadStatus();
  };
}

async function loadProfile() {
  const p = await api("/api/profile");
  const form = $("#profile-form");
  form.full_name.value = p.full_name || "";
  form.headline.value = p.headline || "";
  form.skills.value = p.skills || "";
  form.pitch.value = p.pitch || "";
  $("#resume-name").textContent = p.resume_name ? `Current file: ${p.resume_name}` : "No resume uploaded yet.";
  const importResume = $("#import-resume-name");
  if (importResume) {
    importResume.textContent = p.resume_name
      ? `Ready to attach: ${p.resume_name}`
      : "No resume loaded yet. Upload a PDF to attach it when you send.";
  }
}

async function loadWatchers() {
  const rows = await api("/api/watchers");
  $("#watcher-list").innerHTML = rows.length ? rows.map((w) => `
    <div class="watcher">
      <div>
        <strong>${escapeHtml(w.keywords)}</strong>
        <p class="meta">${escapeHtml(w.location || "any location")} · ${w.active ? "active" : "paused"}</p>
      </div>
      <div class="actions">
        <button class="ghost" data-toggle="${w.id}">${w.active ? "Pause" : "Resume"}</button>
        <button class="ghost danger" data-del="${w.id}">Remove</button>
      </div>
    </div>
  `).join("") : `<p class="hint">No watchers yet.</p>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;");
}

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.onclick = () => showView(btn.dataset.view);
});

$("#job-list").addEventListener("click", (e) => {
  const item = e.target.closest("[data-id]");
  if (item) openJob(Number(item.dataset.id));
});

$("#job-filter").addEventListener("input", (e) => renderJobs(e.target.value));

async function renderImportPreview() {
  const text = $("#import-text").value.trim();
  if (!text) {
    $("#import-preview").innerHTML = `<div class="empty">Paste a job on the left to preview the professional email.</div>`;
    return;
  }
  try {
    const data = await api("/api/jobs/preview", {
      method: "POST",
      body: formBody({ text, url: $("#import-url").value }),
    });
    const job = data.job;
    $("#import-preview").innerHTML = `
      <p class="kicker">${job.on_target ? "Matching target role" : "Not a target role"}</p>
      <h2>${escapeHtml(job.title)}</h2>
      <p class="meta">${escapeHtml(job.company || "Company not listed")} · ${escapeHtml(job.location || "Location not listed")}</p>
      <p>${(job.roles || []).map((role) => `<span class="role-tag">${escapeHtml(role)}</span>`).join("")}</p>
      ${letterHtml(data.draft.subject, data.draft.body, {
        to: job.recruiter_email,
        matched_skills: data.matched_skills,
        resume_name: data.resume_name,
      })}
    `;
  } catch (err) {
    $("#import-preview").innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
  }
}

let previewTimer;
$("#import-text").addEventListener("input", () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(renderImportPreview, 400);
});
$("#import-url").addEventListener("input", () => {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(renderImportPreview, 400);
});

$("#import-resume").addEventListener("change", async (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const body = new FormData();
  body.append("resume", file);
  try {
    const profile = await api("/api/profile/resume", { method: "POST", body });
    toast(`Resume loaded: ${profile.resume_name}`);
    loadProfile();
    renderImportPreview();
  } catch (err) {
    toast(err.message);
  }
});

$("#import-btn").onclick = async () => {
  try {
    const resumeFile = $("#import-resume")?.files?.[0];
    if (resumeFile) {
      const body = new FormData();
      body.append("resume", resumeFile);
      await api("/api/profile/resume", { method: "POST", body });
    }
    const data = await api("/api/jobs/import", {
      method: "POST",
      body: formBody({ text: $("#import-text").value, url: $("#import-url").value }),
    });
    if (!data.drafts?.length) {
      await api(`/api/jobs/${data.job.id}/draft`, { method: "POST" });
    }
    toast("Professional draft ready in Inbox.");
    $("#import-text").value = "";
    showView("inbox");
    await loadJobs();
    await loadStatus();
    openJob(data.job.id);
  } catch (err) {
    toast(err.message);
  }
};

$("#watch-add").onclick = async () => {
  const keywords = $("#watch-keywords").value.trim();
  if (!keywords) return toast("Add at least one keyword");
  await api("/api/watchers", {
    method: "POST",
    body: formBody({ keywords, location: $("#watch-location").value }),
  });
  $("#watch-keywords").value = "";
  loadWatchers();
};

$("#watch-run").onclick = async () => {
  const result = await api("/api/watchers/run", { method: "POST" });
  toast(`Scanned ${result.scanned}, matched ${result.matched || 0} target roles, imported ${result.imported}`);
  loadJobs();
  loadStatus();
  loadWatchers();
};

$("#watcher-list").addEventListener("click", async (e) => {
  if (e.target.dataset.toggle) {
    await api(`/api/watchers/${e.target.dataset.toggle}/toggle`, { method: "POST" });
    loadWatchers();
  }
  if (e.target.dataset.del) {
    await api(`/api/watchers/${e.target.dataset.del}`, { method: "DELETE" });
    loadWatchers();
  }
});

$("#profile-form").onsubmit = async (e) => {
  e.preventDefault();
  const form = e.target;
  const body = new FormData();
  body.append("full_name", form.full_name.value);
  body.append("headline", form.headline.value);
  body.append("skills", form.skills.value);
  body.append("pitch", form.pitch.value);
  if (form.resume.files[0]) body.append("resume", form.resume.files[0]);
  await api("/api/profile", { method: "POST", body });
  toast("Profile saved");
  loadProfile();
};

async function loadRoles() {
  const roles = await api("/api/roles");
  $("#role-bar").innerHTML = roles.map((role) => (
    `<a class="role-chip" href="${escapeAttr(role.linkedin_url)}" target="_blank" rel="noreferrer">${escapeHtml(role.label)} on LinkedIn</a>`
  )).join("");
}

$("#refresh-jobs").onclick = async () => {
  $("#refresh-jobs").disabled = true;
  try {
    const result = await api("/api/watchers/run", { method: "POST" });
    toast(`Loaded ${result.imported} new matches from ${result.matched || 0} target-role postings`);
    await loadJobs();
    await loadStatus();
  } catch (err) {
    toast(err.message);
  } finally {
    $("#refresh-jobs").disabled = false;
  }
};

loadRoles();
loadStatus();
loadJobs();
loadProfile();
loadWatchers();
