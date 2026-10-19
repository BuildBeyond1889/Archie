// Archie Coach: connects VSCodium to Archie's Workshop on this PC (127.0.0.1 only; nothing goes online).
// It tells Archie which file and line you're on, asks Archie to explain or check your code, and shows
// Archie's hints right on the line they're about.
const vscode = require("vscode");
const fs = require("fs");
const path = require("path");

let key = "", watching = true, status, out, deco, diags, sendTimer, hintTimer, lastSent = "";

function cfg(k) { return vscode.workspace.getConfiguration("archieCoach").get(k); }
function base() { return "http://127.0.0.1:" + (cfg("port") || 8765) + "/api/ws/"; }
function readKey() {
  try { key = fs.readFileSync(path.join(cfg("archieFolder") || "D:\\Archie", "Workshop", ".token"), "utf8").trim(); } catch (e) { key = ""; }
  return key;
}
async function call(p, body) {
  if (!key && !readKey()) throw new Error("Can't find Archie. Is Archie running? (Settings: Archie Coach > Archie Folder)");
  const r = await fetch(base() + p, { method: body ? "POST" : "GET", headers: { "X-Archie-Key": key, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (r.status === 403) { readKey(); throw new Error("Archie didn't accept the connection. Restart Archie and try again."); }
  return r.json();
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitJob(r) {
  if (!r || !r.job) return r || {};
  for (let i = 0; i < 600; i++) {
    await sleep(1200);
    const j = await call("job?id=" + r.job);
    if (j.status !== "working") return j.result || {};
  }
  return { error: "Archie took too long." };
}
function show(title, text) {
  out.appendLine("── " + title + " ──");
  out.appendLine(text || "");
  out.appendLine("");
  out.show(true);
}
async function withProgress(title, fn) {
  return vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "Archie: " + title, cancellable: false }, fn);
}

function editorState() {
  const ed = vscode.window.activeTextEditor;
  if (!ed || ed.document.uri.scheme !== "file") return null;
  const sel = ed.selection;
  return { file: ed.document.uri.fsPath, line: sel.active.line + 1, selection: sel.isEmpty ? "" : ed.document.getText(sel).slice(0, 2000), language: ed.document.languageId };
}
function scheduleSend() {
  if (!watching) return;
  clearTimeout(sendTimer);
  sendTimer = setTimeout(async () => {
    const s = editorState();
    if (!s) return;
    const sig = s.file + ":" + s.line + ":" + s.selection.length;
    if (sig === lastSent) return;
    lastSent = sig;
    try { await call("editor", s); setStatus(true); } catch (e) { setStatus(false); }
  }, 1500);
}
function setStatus(ok) {
  status.text = watching ? (ok ? "$(eye) Archie" : "$(eye-closed) Archie (not running)") : "$(circle-slash) Archie off";
  status.tooltip = watching ? "Archie is watching along. Click to turn it off." : "Archie isn't watching. Click to turn it on.";
}
async function refreshHints() {
  const ed = vscode.window.activeTextEditor;
  if (!ed || !watching || ed.document.uri.scheme !== "file") return;
  try {
    const d = await call("hints?file=" + encodeURIComponent(ed.document.uri.fsPath));
    const opts = (d.hints || []).filter((h) => h.line >= 1 && h.line <= ed.document.lineCount).map((h) => ({
      range: ed.document.lineAt(h.line - 1).range,
      hoverMessage: new vscode.MarkdownString("**Archie:** " + h.text),
      renderOptions: { after: { contentText: "   Archie: " + (h.text.length > 90 ? h.text.slice(0, 90) + "…" : h.text) } },
    }));
    ed.setDecorations(deco, opts);
    // What the real checkers found (compiler, ruff, node): squiggles in the code and entries in the Problems panel.
    const D = (d.problems || []).filter((p) => p.line >= 1 && p.line <= ed.document.lineCount).map((p) => {
      const line = ed.document.lineAt(p.line - 1);
      const start = p.col && p.col > 0 && p.col - 1 < line.text.length ? p.col - 1 : line.firstNonWhitespaceCharacterIndex;
      const dg = new vscode.Diagnostic(new vscode.Range(p.line - 1, start, p.line - 1, line.text.length || start + 1), p.msg,
        p.sev === "error" ? vscode.DiagnosticSeverity.Error : vscode.DiagnosticSeverity.Warning);
      dg.source = "Archie";
      if (p.code) dg.code = p.code;
      return dg;
    });
    diags.set(ed.document.uri, D);
  } catch (e) { /* Archie isn't running: nothing to show */ }
}

function activate(context) {
  out = vscode.window.createOutputChannel("Archie");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  status.command = "archieCoach.toggle";
  setStatus(true);
  status.show();
  diags = vscode.languages.createDiagnosticCollection("archie");
  deco = vscode.window.createTextEditorDecorationType({ after: { color: new vscode.ThemeColor("editorCodeLens.foreground"), fontStyle: "italic", margin: "0 0 0 1em" },
    backgroundColor: "rgba(198,244,50,0.06)", isWholeLine: true });

  context.subscriptions.push(out, status, deco, diags,
    vscode.window.onDidChangeTextEditorSelection(scheduleSend),
    vscode.window.onDidChangeActiveTextEditor(() => { scheduleSend(); refreshHints(); }),
    vscode.workspace.onDidSaveTextDocument(() => { setTimeout(refreshHints, 2500); setTimeout(refreshHints, 6000); }),
    vscode.commands.registerCommand("archieCoach.toggle", () => {
      watching = !watching; setStatus(true);
      if (!watching && vscode.window.activeTextEditor) { vscode.window.activeTextEditor.setDecorations(deco, []); diags.clear(); }
    }),
    vscode.commands.registerCommand("archieCoach.explain", async () => {
      const s = editorState();
      if (!s) return;
      try {
        const res = await withProgress(s.selection ? "reading what you selected…" : "reading line " + s.line + "…", async () => waitJob(await call("ask", s)));
        if (res.error) return vscode.window.showWarningMessage("Archie: " + res.error);
        show(s.selection ? "What this does" : "Line " + s.line + " of " + path.basename(s.file), res.text);
      } catch (e) { vscode.window.showWarningMessage(e.message); }
    }),
    vscode.commands.registerCommand("archieCoach.check", async () => {
      const ed = vscode.window.activeTextEditor;
      if (!ed) return;
      await ed.document.save();
      try {
        const res = await withProgress("running and checking your step…", async () => waitJob(await call("check_file", { file: ed.document.uri.fsPath })));
        if (res.error) return vscode.window.showWarningMessage("Archie: " + res.error);
        show(res.pass ? "Step done" : "Not quite yet", (res.feedback || "") + (res.hint ? "\n\nHint: " + res.hint : ""));
        if (res.pass) vscode.window.showInformationMessage("Archie: step done. The next one is in the Workshop.");
        refreshHints();
      } catch (e) { vscode.window.showWarningMessage(e.message); }
    }),
    vscode.commands.registerCommand("archieCoach.hint", async () => {
      const ed = vscode.window.activeTextEditor;
      if (!ed) return;
      try {
        const res = await withProgress("thinking of a hint…", async () => waitJob(await call("hint", { file: ed.document.uri.fsPath })));
        if (res.error) return vscode.window.showWarningMessage("Archie: " + res.error);
        show("Hint", res.text);
      } catch (e) { vscode.window.showWarningMessage(e.message); }
    })
  );
  hintTimer = setInterval(refreshHints, 3000);
  context.subscriptions.push({ dispose: () => clearInterval(hintTimer) });
  scheduleSend();
}
function deactivate() {}
module.exports = { activate, deactivate };
