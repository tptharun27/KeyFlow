"""
KeyFlow - run this on your PC, control it from your phone on the same Wi-Fi.

  python server.py

Hotkeys on the PC (work even while another window has focus):
  F8  stop typing immediately
  F9  pause / resume
"""
import functools
import hmac
import hashlib
import logging
import math
import os
import random
import secrets
import socket
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request
from pynput.keyboard import Controller, Key, Listener
import customtkinter as ctk
from PIL import Image
import qrcode

BASE = Path(__file__).parent

def find_free_port(start_port):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('0.0.0.0', port)) != 0:
                return port
    return start_port

PORT = find_free_port(int(os.environ.get("KEYFLOW_PORT", "8765")))

PIN_FILE = Path.home() / ".keyflow_pin"
if os.environ.get("KEYFLOW_PIN"):
    PIN = os.environ.get("KEYFLOW_PIN")
elif PIN_FILE.exists():
    PIN = PIN_FILE.read_text().strip()
else:
    PIN = f"{secrets.randbelow(10**6):06d}"
    try:
        PIN_FILE.write_text(PIN)
    except Exception:
        pass

MAX_CHARS = 200_000
MODES = ("code", "shift", "enter")

PAGE = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1020">
<title>KeyFlow</title>
<style>
:root{
  --text:#f2f6fc; --mute:rgba(235,242,255,.62); --mint:#a855f7; --mint-ink:#ffffff; --red:#ff8f8f;
  --glass-bg:linear-gradient(135deg,rgba(255,255,255,.17),rgba(255,255,255,.06));
  --glass-edge:rgba(255,255,255,.2);
  --inner:rgba(255,255,255,.1);
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,Menlo,monospace;
}
*{box-sizing:border-box;margin:0}
html{background:#0b1020;color:var(--text);font:16px/1.45 var(--sans);-webkit-text-size-adjust:100%}
body{min-height:100vh;padding:env(safe-area-inset-top) 0 0}
body::before{content:"";position:fixed;inset:-15%;z-index:-1;background:
  radial-gradient(42% 34% at 18% 16%,rgba(124,92,255,.62),transparent 70%),
  radial-gradient(38% 32% at 88% 28%,rgba(36,196,182,.50),transparent 70%),
  radial-gradient(46% 38% at 26% 84%,rgba(255,105,150,.42),transparent 70%),
  radial-gradient(34% 30% at 92% 90%,rgba(60,130,255,.45),transparent 70%)}
[hidden]{display:none!important}
button,input,textarea{font:inherit;color:inherit}
button{-webkit-tap-highlight-color:transparent}
:focus-visible{outline:2px solid var(--mint);outline-offset:2px}

main{max-width:560px;margin:0 auto;padding:16px 14px calc(140px + env(safe-area-inset-bottom));display:grid;gap:14px}
header{display:flex;align-items:center;justify-content:space-between;padding:4px 4px}
h1{font-size:23px;font-weight:700;letter-spacing:-.02em}

/* glass: only top-level surfaces blur; nested pieces stay light */
.card,.pill,.dock>div,.toast,#login .box{
  position:relative;background:var(--glass-bg);border:1px solid var(--glass-edge);
  -webkit-backdrop-filter:blur(26px) saturate(190%);backdrop-filter:blur(26px) saturate(190%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.4),inset 0 -1px 0 rgba(255,255,255,.06),0 14px 36px rgba(3,6,20,.35)}
.card::before,#login .box::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  background:radial-gradient(120% 60% at 10% -10%,rgba(255,255,255,.22),transparent 55%)}
.card{border-radius:28px;padding:16px;overflow:hidden}
.card>*{position:relative}
.card h2{font-size:15px;font-weight:600;margin-bottom:12px}
.hint{font-size:13px;color:var(--mute);margin-top:10px}
.pill{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--mute);padding:7px 13px;border-radius:99px}
.pill i{width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 10px var(--red)}
.pill.on i{background:var(--mint);box-shadow:0 0 10px var(--mint)}

.gbtn,.chip,.step,.seg{background:var(--inner);border:1px solid rgba(255,255,255,.14);box-shadow:inset 0 1px 0 rgba(255,255,255,.25)}
.gbtn{display:flex;align-items:center;gap:6px;border-radius:99px;padding:8px 13px;font-size:14px;cursor:pointer}
.gbtn svg{width:17px;height:17px;flex:none}
.gbtn:disabled{opacity:.35;cursor:default}
.gbtn:active:not(:disabled){background:rgba(255,255,255,.2)}

/* the tape */
.tape-card{padding:0}
.tools{display:flex;gap:8px;justify-content:flex-end;padding:12px 12px 0}
.tools.off{visibility:hidden}
#text,#tape{display:block;width:100%;height:220px;padding:12px 18px 16px;background:none;border:0;resize:none;
  font:14px/1.6 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;tab-size:4}
#text::placeholder{color:var(--mute)}
#tape{overflow:hidden;display:flex;flex-direction:column;justify-content:center;
  -webkit-mask-image:linear-gradient(transparent 0,#000 18%,#000 82%,transparent 100%);
  mask-image:linear-gradient(transparent 0,#000 18%,#000 82%,transparent 100%)}
#tape .line{white-space:pre-wrap}
#tape .done{color:var(--mute)}
#tape .caret{display:inline-block;width:.6em;height:1.15em;background:var(--mint);vertical-align:text-bottom;
  border-radius:2px;box-shadow:0 0 12px var(--mint);animation:blink 1s steps(2,jump-none) infinite}
.meta{display:flex;justify-content:space-between;gap:12px;padding:10px 18px;font-size:13px;color:var(--mute);border-top:1px solid rgba(255,255,255,.12)}
.bar{height:5px;background:rgba(255,255,255,.1)}
.bar i{display:block;height:100%;width:0;background:var(--mint);box-shadow:0 0 12px var(--mint);transition:width .25s linear}
@keyframes blink{50%{opacity:0}}

/* speed */
.speedtop{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
.readout{display:flex;align-items:baseline;gap:10px}
.readout b{font-size:46px;line-height:1;font-weight:700;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.readout span{color:var(--mute);font-size:13px;line-height:1.3}
.nudge{display:flex;gap:8px}
.nudge button{width:46px;height:46px;border-radius:50%;font-size:22px;padding:0;justify-content:center}
input[type=range]{--p:50%;width:100%;height:36px;background:none;-webkit-appearance:none;appearance:none}
input[type=range]::-webkit-slider-runnable-track{height:8px;border-radius:8px;background:linear-gradient(90deg,var(--mint) var(--p),rgba(255,255,255,.16) var(--p))}
input[type=range]::-moz-range-track{height:8px;border-radius:8px;background:rgba(255,255,255,.16)}
input[type=range]::-moz-range-progress{height:8px;border-radius:8px;background:var(--mint)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:30px;height:30px;margin-top:-11px;border-radius:50%;
  background:linear-gradient(#fff,#dfe8f5);border:0;box-shadow:0 3px 10px rgba(0,0,0,.4),inset 0 1px 0 #fff}
input[type=range]::-moz-range-thumb{width:30px;height:30px;border-radius:50%;background:#eef3fb;border:0;box-shadow:0 3px 10px rgba(0,0,0,.4)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.chip{padding:8px 14px;border-radius:99px;font-size:14px;cursor:pointer}
.chip[aria-pressed=true]{background:var(--mint);color:var(--mint-ink);font-weight:600;border-color:transparent}

/* line breaks: sliding glass thumb */
.seg{--i:0;position:relative;display:grid;grid-template-columns:repeat(4,1fr);padding:4px;border-radius:18px}
.seg::before{content:"";position:absolute;top:4px;bottom:4px;left:4px;width:calc((100% - 8px)/4);border-radius:14px;
  transform:translateX(calc(var(--i)*100%));transition:transform .3s cubic-bezier(.3,1.35,.5,1);
  background:linear-gradient(rgba(255,255,255,.34),rgba(255,255,255,.16));box-shadow:inset 0 1px 0 rgba(255,255,255,.5),0 4px 12px rgba(0,0,0,.25)}
.seg button{position:relative;border:0;background:none;padding:11px 2px;font-size:14px;color:var(--mute);cursor:pointer;transition:color .2s}
.seg button[aria-pressed=true]{color:var(--text);font-weight:600}

.row{display:flex;align-items:center;justify-content:space-between;gap:12px}
.row + .row,.sep{margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.12)}
.row small{display:block;color:var(--mute);font-size:13px}
.step{display:flex;align-items:center;gap:2px;border-radius:16px;padding:4px}
.step button{width:40px;height:40px;border:0;border-radius:12px;background:rgba(255,255,255,.12);font-size:20px;cursor:pointer}
.step output{min-width:50px;text-align:center;font-variant-numeric:tabular-nums}
.switch{position:relative;width:54px;height:32px;flex:none}
.switch input{position:absolute;inset:0;opacity:0;margin:0;cursor:pointer;z-index:1}
.switch span{position:absolute;inset:0;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.14);border-radius:99px;transition:background .2s}
.switch span::after{content:"";position:absolute;left:3px;top:3px;width:24px;height:24px;border-radius:50%;background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.35);transition:transform .25s cubic-bezier(.3,1.35,.5,1)}
.switch input:checked + span{background:var(--mint)}
.switch input:checked + span::after{transform:translateX(22px)}
.switch input:focus-visible + span{outline:2px solid var(--mint);outline-offset:2px}

details summary{cursor:pointer;font-weight:600;font-size:15px;list-style:none;display:flex;justify-content:space-between}
details summary::-webkit-details-marker{display:none}
details summary::after{content:"+";color:var(--mute);font-size:20px;line-height:1}
details[open] summary::after{content:"\2212"}
.snips{display:grid;gap:8px;margin-top:12px}
.snips:empty::after{content:"Nothing saved yet. Save the current text to reuse it later.";color:var(--mute);font-size:13px}
.snip{display:flex;gap:8px}
.snip button{border:1px solid rgba(255,255,255,.14);background:var(--inner);border-radius:14px;cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.2)}
.snip button:first-child{flex:1;text-align:left;padding:12px 14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.snip button:last-child{width:46px;color:var(--mute)}
.link{background:none;border:0;color:var(--mint);padding:12px 0 0;font-size:14px;cursor:pointer}
.forget{justify-self:center;background:none;border:0;color:var(--mute);font-size:13px;padding:6px;cursor:pointer;text-decoration:underline;text-underline-offset:3px}

/* dock + toast */
.dock{position:fixed;left:12px;right:12px;bottom:calc(10px + env(safe-area-inset-bottom))}
.dock>div{max-width:536px;margin:0 auto;padding:8px;display:flex;gap:8px;border-radius:32px}
.btn{flex:1;min-height:56px;border:0;border-radius:24px;font-weight:700;font-size:17px;cursor:pointer;transition:transform .12s}
.btn:active{transform:scale(.97)}
.btn.go{background:linear-gradient(#c084fc,var(--mint));color:var(--mint-ink);box-shadow:inset 0 1px 0 rgba(255,255,255,.7),0 6px 20px rgba(168,85,247,.35)}
.btn.go:disabled{opacity:.6}
.btn.stop{flex:0 0 104px;background:rgba(255,120,120,.16);border:1px solid rgba(255,140,140,.35);color:var(--red)}
.toast{position:fixed;left:50%;bottom:calc(98px + env(safe-area-inset-bottom));z-index:5;display:flex;align-items:center;gap:14px;
  padding:11px 12px 11px 18px;border-radius:99px;font-size:14px;white-space:nowrap;max-width:calc(100vw - 24px);
  opacity:0;transform:translate(-50%,16px);pointer-events:none;transition:opacity .2s,transform .25s cubic-bezier(.3,1.35,.5,1)}
.toast.show{opacity:1;transform:translate(-50%,0);pointer-events:auto}
.toast button{border:0;background:rgba(255,255,255,.18);color:var(--mint);font-weight:600;border-radius:99px;padding:7px 14px;cursor:pointer}
.toast span{overflow:hidden;text-overflow:ellipsis}

/* login */
#login{min-height:100vh;display:grid;place-content:center;padding:24px}
#login .box{display:grid;gap:14px;justify-items:center;text-align:center;padding:28px 24px;border-radius:32px;width:min(340px,100%)}
#login .box>*{position:relative}
#login input{width:100%;padding:14px;border-radius:18px;border:1px solid rgba(255,255,255,.22);background:rgba(255,255,255,.1);
  text-align:center;font:600 24px var(--mono);letter-spacing:.3em}
#login p{color:var(--mute);font-size:14px}
#login .err{color:var(--red);min-height:1.4em;font-size:14px}
#login .btn{flex:none;width:100%}

@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>
</head>
<body>

<section id="login" hidden>
  <div class="box">
    <h1>KeyFlow</h1>
    <p>Enter the PIN shown in the window where the script is running on your PC.</p>
    <input id="pin" inputmode="numeric" autocomplete="off" maxlength="12" aria-label="PIN">
    <div class="err" id="loginErr"></div>
    <button class="btn go" id="connect">Connect</button>
  </div>
</section>

<main id="app" hidden>
  <header>
    <h1>KeyFlow</h1>
    <div class="pill" id="pill"><i></i><span>Connecting</span></div>
  </header>

  <section class="card tape-card" aria-label="Text to type">
    <div class="tools" id="tools">
      <button class="gbtn" id="paste"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/></svg>Paste</button>
      <button class="gbtn" id="clear"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>Clear</button>
    </div>
    <textarea id="text" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off"
      placeholder="Paste or write what your PC should type"></textarea>
    <div id="tape" hidden aria-live="off"></div>
    <div class="meta"><span id="count">0 characters</span><span id="note"></span></div>
    <div class="bar"><i id="fill"></i></div>
  </section>

  <section class="card">
    <h2>Speed</h2>
    <div class="speedtop">
      <div class="readout"><b id="cps">14</b><span>characters per second<br>about <span id="wpm">168</span> words per minute</span></div>
      <div class="nudge">
        <button class="gbtn" id="slower" aria-label="Slower">&minus;</button>
        <button class="gbtn" id="faster" aria-label="Faster">+</button>
      </div>
    </div>
    <input type="range" id="speed" min="0" max="100" step="1" aria-label="Typing speed">
    <div class="chips" id="chips"></div>
    <div class="row sep">
      <div><b>Human rhythm</b><small>Varies the gap between keys</small></div>
      <label class="switch"><input type="checkbox" id="human" aria-label="Human rhythm"><span></span></label>
    </div>
  </section>

  <section class="card">
    <h2>Line breaks</h2>
    <div class="seg" id="seg"></div>
    <p class="hint" id="modeHint"></p>
    <div class="row sep">
      <div><b>Start delay</b><small>Time to click into the target window</small></div>
      <div class="step"><button id="dMinus" aria-label="Shorter delay">&minus;</button><output id="delay">5 s</output><button id="dPlus" aria-label="Longer delay">+</button></div>
    </div>
  </section>

  <section class="card">
    <details>
      <summary>Saved snippets</summary>
      <div class="snips" id="snips"></div>
      <button class="link" id="save">Save current text</button>
    </details>
  </section>

  <button class="forget" id="forget">Forget the PIN on this phone</button>
</main>

<div class="toast" id="toast" role="status"></div>

<div class="dock" id="dock" hidden>
  <div>
    <button class="btn go" id="go">Start typing</button>
    <button class="btn stop" id="stop" hidden>Stop</button>
  </div>
</div>

<script>
const $ = s => document.querySelector(s);
const MODES = {
  code:  ["Code",        "Presses Enter, then overwrites the editor's auto-indent so your original indentation is kept exactly."],
  shift: ["Shift+Enter", "Adds a line break without sending. Use it in WhatsApp, Slack, Discord and Teams."],
  enter: ["Enter",       "Plain Enter at every line break. Best for editors with auto-indent turned off."]
};
const PRESETS = [["Slow",5],["Natural",14],["Fast",40],["Turbo",150]];
const KEY = "keyflow:v1", SKEY = "keyflow:snips";

const cpsOf = v => Math.max(1, Math.round(Math.pow(200, v / 100)));
const vOf = c => Math.round(100 * Math.log(Math.max(1, c)) / Math.log(200));
const clampC = c => Math.min(200, Math.max(1, Math.round(c)));
const stepOf = c => c < 20 ? 1 : c < 60 ? 5 : 10;

let saved = {}; try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let S = Object.assign({text:"", cps:14, mode:"code", human:false, delay:5}, saved);
if (saved.cps === undefined && saved.v !== undefined) S.cps = cpsOf(saved.v);
delete S.v;
let PIN = localStorage.getItem("keyflow:pin") || "";
let st = {state:"idle", typed:0, total:0};
let snips = []; try { snips = JSON.parse(localStorage.getItem(SKEY) || "[]"); } catch (e) {}
let cache = {key:"", chars:[]};

const qs = new URLSearchParams(location.search);
if (qs.get("pin")) { PIN = qs.get("pin"); localStorage.setItem("keyflow:pin", PIN); history.replaceState({}, "", location.pathname); }

const save = () => localStorage.setItem(KEY, JSON.stringify(S));
const fmt = s => s < 60 ? Math.ceil(s) + " s" : Math.floor(s / 60) + " min " + Math.round(s % 60) + " s";
const busy = () => st.state !== "idle" && st.state !== "done" && st.state !== "stopped";
const buzz = () => navigator.vibrate && navigator.vibrate(10);
document.addEventListener("click", e => { if (e.target.closest("button")) buzz(); });

let toastTimer;
function toast(msg, action, fn) {
  const t = $("#toast"); t.replaceChildren();
  const s = document.createElement("span"); s.textContent = msg; t.append(s);
  if (action) {
    const b = document.createElement("button"); b.textContent = action;
    b.onclick = () => { fn(); t.classList.remove("show"); };
    t.append(b);
  }
  t.classList.add("show"); clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 5000);
}

async function api(path, body) {
  const r = await fetch("/api/" + path, {
    method: body === undefined ? "GET" : "POST",
    headers: {"Content-Type": "application/json", "X-Pin": PIN},
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 || r.status === 429) { showLogin(data.error); throw new Error("auth"); }
  if (!r.ok) throw new Error(data.error || "Request failed");
  return data;
}

/* ---------- login ---------- */
function showLogin(msg) {
  $("#app").hidden = true; $("#dock").hidden = true; $("#login").hidden = false;
  $("#loginErr").textContent = msg || "";
}
$("#connect").onclick = () => {
  PIN = $("#pin").value.trim();
  localStorage.setItem("keyflow:pin", PIN);
  $("#login").hidden = true; poll();
};
$("#pin").addEventListener("keydown", e => { if (e.key === "Enter") $("#connect").click(); });
$("#forget").onclick = () => { localStorage.removeItem("keyflow:pin"); PIN = ""; showLogin(); };

/* ---------- text tools ---------- */
function setText(t) { S.text = t; $("#text").value = t; save(); drawMeta(); }
$("#clear").onclick = () => {
  if (!S.text) return;
  const old = S.text; setText("");
  $("#text").focus();
  toast("Text cleared", "Undo", () => { setText(old); $("#text").focus(); });
};
$("#paste").onclick = async () => {
  try {
    const t = await navigator.clipboard.readText();
    if (!t) return toast("Clipboard is empty");
    const old = S.text; setText(t);
    toast("Pasted from clipboard", old ? "Undo" : null, () => setText(old));
  } catch (e) {
    $("#text").focus();
    toast("Long-press the box and choose Paste");
  }
};
$("#text").addEventListener("input", e => { S.text = e.target.value; save(); drawMeta(); });
$("#text").addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") $("#go").click(); });

/* ---------- speed ---------- */
let speedTimer;
function drawSpeed(fromSlider) {
  const c = S.cps;
  $("#cps").textContent = c; $("#wpm").textContent = Math.round(c * 12);
  const sp = $("#speed");
  if (!fromSlider) sp.value = vOf(c);
  sp.style.setProperty("--p", sp.value + "%");
  document.querySelectorAll(".chip").forEach(b => b.setAttribute("aria-pressed", +b.dataset.c === c));
  drawMeta();
}
function setCps(c, fromSlider) {
  S.cps = clampC(c); save(); drawSpeed(fromSlider);
  clearTimeout(speedTimer);
  if (busy()) speedTimer = setTimeout(() => api("speed", {cps: S.cps}).catch(() => {}), 150);
}
$("#speed").oninput = e => setCps(cpsOf(+e.target.value), true);
$("#slower").onclick = () => setCps(S.cps - stepOf(S.cps - 1));
$("#faster").onclick = () => setCps(S.cps + stepOf(S.cps));
PRESETS.forEach(([name, c]) => {
  const b = document.createElement("button");
  b.className = "chip"; b.dataset.c = c; b.textContent = name + " " + c;
  b.onclick = () => setCps(c);
  $("#chips").append(b);
});

/* ---------- line breaks, delay, rhythm ---------- */
Object.entries(MODES).forEach(([k, [label]]) => {
  const b = document.createElement("button");
  b.textContent = label; b.dataset.k = k;
  b.onclick = () => { S.mode = k; save(); drawMode(); };
  $("#seg").append(b);
});
function drawMode() {
  document.querySelectorAll("#seg button").forEach(b => b.setAttribute("aria-pressed", b.dataset.k === S.mode));
  $("#seg").style.setProperty("--i", Object.keys(MODES).indexOf(S.mode));
  $("#modeHint").textContent = MODES[S.mode][1];
  drawMeta();
}
$("#human").onchange = e => { S.human = e.target.checked; save(); };
const drawDelay = () => $("#delay").textContent = S.delay + " s";
$("#dMinus").onclick = () => { S.delay = Math.max(0, S.delay - 1); save(); drawDelay(); };
$("#dPlus").onclick  = () => { S.delay = Math.min(30, S.delay + 1); save(); drawDelay(); };

function norm(t) {
  t = t.replace(/\r\n?/g, "\n");
  return t;
}
function drawMeta() {
  $("#clear").disabled = !S.text;
  if (busy()) return;
  const t = S.text, n = Array.from(norm(t)).length;
  const lines = t ? t.split(/\r\n|\r|\n/).length : 0;
  $("#count").textContent = n.toLocaleString() + " characters \u00b7 " + lines + " lines";
  $("#note").textContent = n ? "about " + fmt(n / S.cps) : "";
}

/* ---------- snippets ---------- */
function drawSnips() {
  const box = $("#snips"); box.textContent = "";
  snips.forEach((s, i) => {
    const row = document.createElement("div"); row.className = "snip";
    const load = document.createElement("button"); load.textContent = s.name;
    load.onclick = () => { if (busy()) return; setText(s.text); window.scrollTo({top: 0, behavior: "smooth"}); toast("Loaded " + s.name); };
    const del = document.createElement("button"); del.textContent = "\u00d7"; del.setAttribute("aria-label", "Delete " + s.name);
    del.onclick = () => {
      const gone = snips.splice(i, 1)[0];
      localStorage.setItem(SKEY, JSON.stringify(snips)); drawSnips();
      toast("Snippet deleted", "Undo", () => { snips.splice(i, 0, gone); localStorage.setItem(SKEY, JSON.stringify(snips)); drawSnips(); });
    };
    row.append(load, del); box.append(row);
  });
}
$("#save").onclick = () => {
  if (!S.text.trim()) return toast("Add some text first");
  const name = prompt("Name this snippet", S.text.trim().split("\n")[0].slice(0, 30));
  if (!name) return;
  snips.unshift({name, text: S.text});
  localStorage.setItem(SKEY, JSON.stringify(snips)); drawSnips();
  toast("Saved " + name);
};

/* ---------- run ---------- */
$("#go").onclick = async () => {
  try {
    if (st.state === "typing" || st.state === "paused") return await api("pause", {});
    if (!S.text.trim()) { toast("Add some text first"); return; }
    await api("start", {text: S.text, cps: S.cps, newline: S.mode, humanize: S.human, delay: S.delay});
  } catch (e) { if (e.message !== "auth") toast(e.message); }
  poll();
};
$("#stop").onclick = () => api("stop", {}).then(poll).catch(() => {});

/* ---------- live state ---------- */
function drawTape() {
  const tape = $("#tape"), key = S.mode + "\u0000" + S.text;
  if (cache.key !== key) cache = {key, chars: Array.from(norm(S.text))};
  const c = cache.chars, i = Math.min(st.typed, c.length);
  const before = c.slice(Math.max(0, i - 260), i).join(""), after = c.slice(i, i + 460).join("");
  const wrap = document.createElement("div"); wrap.className = "line";
  const a = document.createElement("span"); a.className = "done"; a.textContent = (i > 260 ? "\u2026" : "") + before;
  const caret = document.createElement("span"); caret.className = "caret";
  const b = document.createElement("span"); b.textContent = after + (c.length - i > 460 ? "\u2026" : "");
  wrap.append(a, caret, b); tape.replaceChildren(wrap);
}

function render() {
  const run = busy(), total = st.total || 1;
  $("#text").hidden = run; $("#tape").hidden = !run; $("#text").readOnly = run;
  $("#tools").classList.toggle("off", run);
  $("#stop").hidden = !run;
  $("#fill").style.width = (run || st.state === "done" ? 100 * st.typed / total : 0) + "%";
  document.title = st.state === "countdown" ? "Starting\u2026 \u00b7 KeyFlow"
    : run ? Math.round(100 * st.typed / total) + "% \u00b7 KeyFlow" : "KeyFlow";

  const go = $("#go"); go.disabled = false;
  if (st.state === "countdown") { go.textContent = "Starting in " + st.countdown; go.disabled = true; $("#count").textContent = "Click into the window on your PC"; $("#note").textContent = ""; drawTape(); }
  else if (st.state === "typing" || st.state === "paused") {
    go.textContent = st.state === "paused" ? "Resume" : "Pause";
    $("#count").textContent = st.typed.toLocaleString() + " of " + st.total.toLocaleString() + (st.state === "paused" ? " \u00b7 paused" : "");
    const left = (st.total - st.typed) / Math.max(1, st.cps || S.cps);
    $("#note").textContent = st.state === "paused" ? "" : fmt(left) + " left";
    drawTape();
  } else {
    go.textContent = st.state === "done" || st.state === "stopped" ? "Type again" : "Start typing";
    if (st.state === "done") { $("#count").textContent = "Done \u00b7 " + st.total.toLocaleString() + " characters typed"; $("#note").textContent = ""; }
    else if (st.state === "stopped") { $("#count").textContent = "Stopped at " + st.typed.toLocaleString() + " of " + st.total.toLocaleString(); $("#note").textContent = ""; }
    else drawMeta();
  }
}

async function poll() {
  if (!PIN) return showLogin();
  try {
    const prev = st.state;
    st = await api("status");
    $("#pill").className = "pill on"; $("#pill span").textContent = st.host;
    $("#app").hidden = false; $("#dock").hidden = false; $("#login").hidden = true;
    if (prev !== st.state && (st.state === "done" || st.state === "stopped")) navigator.vibrate && navigator.vibrate(120);
    render();
  } catch (e) {
    if (e.message === "auth") return;
    $("#pill").className = "pill"; $("#pill span").textContent = "PC not reachable";
    $("#app").hidden = false;
  }
}

$("#text").value = S.text; $("#human").checked = S.human;
drawSpeed(); drawMode(); drawDelay(); drawSnips();
poll(); setInterval(poll, 350);
</script>
</body>
</html>
'''

app = Flask(__name__)
kb = Controller()

stop_evt = threading.Event()
pause_evt = threading.Event()
lock = threading.Lock()
worker = None
job = {"state": "idle", "typed": 0, "total": 0, "cps": 14.0, "countdown": 0}
fails = {}  # ip -> [failed_count, locked_until]


# ----------------------------------------------------------------- typing ---
def tap(key, *mods):
    for m in mods:
        kb.press(m)
    kb.press(key)
    kb.release(key)
    for m in reversed(mods):
        kb.release(m)


def press_newline(mode, nxt):
    """Insert a line break the way the chosen mode wants it."""
    if mode == "shift":            # chat apps: new line without sending
        tap(Key.enter, Key.shift)
        return
    tap(Key.enter)
    if mode == "code":
        time.sleep(0.3)
        kb.press(Key.space)
        kb.release(Key.space)
        time.sleep(0.05)
        kb.press(Key.shift)
        kb.press(Key.home)
        time.sleep(0.05)
        kb.release(Key.home)
        kb.release(Key.shift)
        time.sleep(0.05)
        kb.press(Key.backspace)
        kb.release(Key.backspace)
        time.sleep(0.05)


def type_char(ch):
    try:
        kb.type(ch)
    except Exception:  # character the keyboard layout cannot produce
        pass


def finish(state):
    job["state"] = state
    job["countdown"] = 0
    pause_evt.clear()


def run_job(text, mode, humanize, delay):
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    n = len(text)

    for s in range(delay, 0, -1):               # time to click the target window
        job["countdown"] = s
        if stop_evt.wait(1):
            return finish("stopped")
    job["countdown"] = 0
    job["state"] = "typing"

    i = 0
    next_t = time.perf_counter()
    while i < n:
        if stop_evt.is_set():
            return finish("stopped")
        if pause_evt.is_set():
            job["state"] = "paused"
            while pause_evt.is_set() and not stop_evt.is_set():
                stop_evt.wait(0.1)
            if stop_evt.is_set():
                return finish("stopped")
            job["state"] = "typing"
            next_t = time.perf_counter()

        cps = max(0.5, float(job["cps"]))       # read each loop: live speed changes
        batch = max(1, math.ceil(cps / 40))     # type small bursts at high speeds
        ch = " "
        for _ in range(batch):
            if i >= n:
                break
            ch = text[i]
            if ch == "\n":
                press_newline(mode, text[i + 1] if i + 1 < n else None)
            else:
                type_char(ch)
            i += 1
        job["typed"] = i

        gap = batch / cps
        if humanize:
            gap *= random.uniform(0.45, 1.7)
            if ch in " \n" and random.random() < 0.12:
                gap += random.uniform(0.1, 0.35)
        next_t += gap
        wait = next_t - time.perf_counter()
        if wait > 0:
            stop_evt.wait(wait)
        elif wait < -0.5:                       # fell far behind, don't sprint
            next_t = time.perf_counter()
    finish("done")


# -------------------------------------------------------------------- API ---
def guarded(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        ip = request.remote_addr
        count, until = fails.get(ip, [0, 0])
        if time.time() < until:
            return jsonify(error="Too many wrong PINs. Wait a minute."), 429
        sent = request.headers.get("X-Pin", "").encode()
        if hmac.compare_digest(sent, PIN.encode()):
            fails.pop(ip, None)
            return fn(*args, **kwargs)
        count += 1
        if count >= 5:
            fails[ip] = [0, time.time() + 60]
        else:
            fails[ip] = [count, 0]
        return jsonify(error="Wrong PIN."), 401
    return wrapper


@app.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/")
def index():
    return PAGE


@app.get("/api/status")
@guarded
def status():
    return jsonify(**job, host=socket.gethostname())


@app.post("/api/start")
@guarded
def start():
    global worker
    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("text", ""))
    if not text:
        return jsonify(error="Nothing to type."), 400
    if len(text) > MAX_CHARS:
        return jsonify(error=f"Text is longer than {MAX_CHARS:,} characters."), 400
    mode = data.get("newline", "code")
    mode = mode if mode in MODES else "code"
    try:
        cps = min(400.0, max(0.5, float(data.get("cps", 14))))
        delay = min(60, max(0, int(data.get("delay", 5))))
    except (TypeError, ValueError):
        return jsonify(error="Invalid speed or delay."), 400

    with lock:
        if worker and worker.is_alive():
            return jsonify(error="Already typing."), 409
        stop_evt.clear()
        pause_evt.clear()
        job.update(state="countdown", typed=0, total=len(text.replace("\r\n", "\n")),
                   cps=cps, countdown=delay)
        worker = threading.Thread(
            target=run_job, args=(text, mode, bool(data.get("humanize")), delay), daemon=True)
        worker.start()
    return jsonify(ok=True)


@app.post("/api/pause")
@guarded
def pause():
    toggle_pause()
    return jsonify(ok=True)


@app.post("/api/stop")
@guarded
def stop():
    stop_evt.set()
    return jsonify(ok=True)


@app.post("/api/speed")
@guarded
def speed():
    data = request.get_json(force=True, silent=True) or {}
    try:
        job["cps"] = min(400.0, max(0.5, float(data.get("cps", job["cps"]))))
    except (TypeError, ValueError):
        return jsonify(error="Invalid speed."), 400
    return jsonify(ok=True)


# ---------------------------------------------------------------- hotkeys ---
def toggle_pause():
    if job["state"] in ("typing", "paused"):
        if pause_evt.is_set():
            pause_evt.clear()
        else:
            pause_evt.set()


def on_key(key):
    if key == Key.f8:
        stop_evt.set()
    elif key == Key.f9:
        toggle_pause()


# ------------------------------------------------------------------- main ---
def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()



VALID_HASHES = ['5e6b6f29d459986dd2c83bc69a0b4a6b6c63c8e824602b2826627311d1234ad5', 'a241c8487db829015fbb518bc0a31799a5482ac47d8a3db0f081bc407e255ee3', 'fb4449e78636a1f23c171fd7a0b875ee30e6e0085db5c1fbdcc8d65965b322a0', '9cc276a89369fb9facd74d67c05a5b97412564fc3e4c62194708e8708e9670ce', '981117b12658df79beaf6276ffaa259c9fc308f631a0637fe865f165a96f26a9', 'a0c9d01e5db4c782c3e65b6b65162e8908bd974f35c39ae665d8abcf10a00a85', 'd7ebf7604fc5cffbb89765984684c50316d128890653cfb2cb6141eb4dfc68cb', 'c852aa196ea9ada9393f4f36ff5c620886abe30dda542fe5e5460fec2a508850', 'b493292fc12d0c70c740a878c3564a7165fc4bce4734e57e0dcbc6ec09571c19', '8b1d7597d31db5f42aa19b51b089789da2d27b796eb053a86adaaaaa4ea451df', '244a11ec752bc079f8a3a71589a9fad9b64065582ba27c1be24427c0e70bfbcf', '1139c29314f800d7f2234bcbd48223691bb9113a3ec5630387116620dccf5b96', '2268bf7e8322b338a5f15bc9eb7ae5d1a7fa84c038015c8957de6daedd6ce4a9', 'dedf8d2165a6df2798733611d8fb9fe171d5977eb5bfb8b4d6c1da035f093efc', '4843e65de2fb4f377812422412ce3774abce9fe600bde051ee8eaf4fdd63d288', '0406670a8d46a88ca3a7f20f85ed7a827d6591ea42e9cdf948a9384f4bd34538', 'cb1b5de2f2d4e9775f219a79667dc90f558c4a61a1a7b566784a92817dc1bc16', '1dc8b60fe01095c0af88d96721525a3f931b18f2356b79c790e8eb6caf0ac098', '9ea02b98ea6bc2609042376a129013c27a3b6ea84f835984f300ffd35abb87b3', '81db9692680f3de40b2085ffc1b7d7a345d847a233405bab72da89ed8b864444', '0de24ba6409d13f01b50874c38d3b24c5e742abdd5fc0e7878b4175a4c38b61b', 'bfb070f135c1a5014f7e5c8c670f575dda0e731bcd9841001ec81cf2d8f7ba12', 'f570a00ab9fdd3063ccbdfa2bc53a3af3184a922f643fc6e93b697a5bf7bb6e8', '2f66007fc7ddc6e153cbad7f851c7cabc8f1c9e5b5826c597b42213484feffea', 'a88c5c03523d550645c8c48fe31bd51a244756dd4ece4ec5cefc5c9c0b009357', '9b34b8fbecf27ac3d7bee4c9747dd13c6fe1d9acf7fe7885434c09b1cb0c614b', '39a340e0cca4d2b6eb5ce6630011a88826a348fa9f6b0ce688008d76b2e1b9a4', '563b5b501d4f114dbc6d9f478a7e41e6bdaf0a3eaf0014f829df888790c514e3', '71c20c155565b29c20a6983f73136deabd858915680b2afaaf8648b9d771c329', 'f4f36dc045a62fb41b912c98469698afed33ca3e03f97400932efc142c52ff5e', 'a1ad8e98b6f266204667c1e1c1c67971025d1845fbeeff716e73045c5edd9f7a', 'c7050f51a252704f4cb9c4d1658660e8c2b667b55514c7a9ad6d09ecb08b7376', '21f4f64494cdaa4d5974af8081056dc50eeecc7fbe0ae65ab72804f7e63fb6f5', 'eb9d89930ef0d052ea6f4b233ebb0c1770c611814a8d458af68fe5d1a01ecddc', '8fd209be5754d155007fc33379e47cf7d7426470c4f81c5d1bb76800d065e785', 'bcdb69c886a457a7abbcd9b08009b4930e5a2da2745066e6db1d9e535905903b', '2c3abe5fb3c97a5a304a571a749e2b286abc29c19b49dd3b04a90b6971565544', '42004d5d44874c3f2ba2c84d097187e797a08a616f41c84315e4572108305067', 'c113bfd96ddd4a036ca37ead1d4f69e04828f746dd47b5933f56fb5c158ca1d8', 'd22d8fb304065ee67eedf70a611bbfd7154cc5a9f37bfa125608836d154064e4', 'f4277108ca32500465cd44a5f23e231e03fcde5779a5720eb6368b2e86b31661', 'cc63152169282514e6a973c3d4bd7b3dbe71c5d549bc2a7339128927593517a1', 'f0c9c188504e7e17d77403d982e681c281c085b6eedd0f8f04c63e873daa0baf', 'af34d6c2161750527fd3c112cb1d9a610edf9169cbdc239c7124bea7c440738c', 'ff73234f9a455b61f435c1b9f0150820425fb414bca7f0dc6741b574fe1b3a71', 'c90c17672e89616488b41753c450a7d165a78d9b25fae67944b603e29fa4e163', 'f1dbc5989b75136637df2ed303e90035eb0c99943d17ce90391485dc37584a9e', 'f1b42181ad2d508a3b39750df753c50cc26ceea0f0224f933ce02e37d831a516', '85da68525723d59165be5e9e8086d8247a4898c844f39b9b096a646600aed976', '08370559861034f4ee2d32b375b552af76b95aa334f3e72983a4c67dffe576ce', 'acfb8c501f4fb8ec4d6805032ffacf81d4155cd5a957a5539f12db338f007581', '1debfcef84b01944ee93f6a05b4609b119b86e360385920793e898b04a00b5ff', 'e98ca2a33cbfc10322a9fca2c715c40e19e8ccfedc5614dcb08577ea1bc72cc8', 'b39d74fd6e1eed6c07922ba9bee77b5646fea1fe431ce16e005996744e662e63', 'c09d7772eeb1441fe4628f03a23a87f370009bfd9a196cd7fd6183516735f346', '4cd61f63f9c8422fe1a463cf415b454ceb0a20230680248d0c7428e2215d45c9', 'e400a0f3b6b48d732c27439ab40b8e11a0ba5704a09e8bd579a51d8ac7ac4358', 'c858ba451041f0bea907342db1103cbd148412450ee4f51e8106f3d37ca5c675', '9d1b2962de415fbf07717c080a3d17c9fe049df2c894ec1e2313069d15b48370', '041a95d5f19007e4c3cb041de38533ae6f6cb8a9996a5a118de00ad7c5114bb4', 'b6aca1e017c7f8dd13457cca725f6268cb0c20b68860b9a7e7fd7d1de0f3cdf1', '561212d834f981f26a5770b0757d2fb027594dcd0d241d4bceb96071cc1d29f4', '6003510f855fdebee0c9b146ee1c45648558045cdf4021be021df136c7c2930f', '45c7c5798f13e464c094bd17ad067a2adb33290eef08a40b83e9d89a636bfc27', 'e2e40d752287254af080af426a0c2627ee1ad7ba6cb83cac1b82bdc957862c0a', 'ada19e2f396eae89ea54a45097f0445c47216edf11f9a8ac1de9d436a1cec4d2', '0cf3919bab235f2eea7c63698d45c893bc1dadfb91cd9e4df111e638db48b617', '0803734a2741aac616e9fc5892ccdc5a51cb817d2e47adcc013ae78a69cafcd6', '39a9948e778868d26967eab796d6e01c1923a5fb7c1e079de318238666f00ec8', '1b9c63f955d198ad827b855052727e0a940f12182e451a9dec1af54284eccdc3', '64470e22d462057fe7440c0304985d5775154085c916628b19f61dcc2344fada', '2ad2d5c3a6c7d359f6d846b160fa054f8d6bc1cc3a750547790b193493716c0d', 'dc78b6710f78312f9efac67a3fb4aa7f269451e17befbbf7bc94216b377759b0', '545ed06ae3a377efd1c257b7174fc9783fd68b056b7bbb5567af4f394b5f89b4', '8fedb5dee88c5e9b46442e84b058933e3acaeef80e5680a306b4dfca3d595a9c', '8be12cac25ecfd214016cf02c7505a04fabb0f3863beb0545c2a88fe40266e8b', 'b7a9ff4ccacc144a4c70cc9b2d0b23369e0792a09fcee46a8458a1b026a5d01a', 'b31fcd160ce16eb758d8b878b8186ad74b97ca80058b6d709be211db48dc35da', 'f150b6622552aecc12b424dd9ac1ca9d66d637a5e8a010caf36ca199285dc91e', '1fe7b368a4b15f83cf79ae71f54db4160351a6fc3ff28e4d70502a055fc01418', '568a1a1d859943c2457ad675e2c25b321c7eaf375bd7b08ac0d4fccb4e209479', '6c45e736ef54b4ee77af270ed0e14d30817496fb1b5d892ea74eadf435ba0c4e', '66f3f500ba7edd52d0d9302af89956afe87e403ecdcb19fdedcd034590772ddb', '17136c6d7dfcd2a3f30e55848dd6c21d73ab283e532877030a7c7942eda2ff58', 'f3bdd61205a74e0e38516c060ce3a162ecde95f98371388ad413e25833836443', 'f3aa61d304f473788843429b4f149d3cb9d223bd5de121acfca8ad275d551cd8', '0a01dc6e687f3b7a65385550597c370a4ef2de21aac3fb051db8885c016749ba', '3befa63f414d13e75339f1b38928d730313958508eb82ad9d4e4b13b3c0d34a4', '790cb0900526dc6c5b7f039704cecb66c6824299935740000822750641e5a486', '61a7718bf60c6c34d00f4dcca732a9b37404c85229a03dc8e838483c73f77e20', '2d42c146ba930d67d2858e4dc8622b12804771f074ab25270a570041a38decda', 'bf3359bd0c1ac970d8781f4982e78106810e7f179316af1cf439c2194ffabd53', '21f7f58cc3319ae58d9901ea4bd57b320c86755f030460dbc733e1de8f3ab565', 'd3c52c65b064c6fa78ac8f7daed7bcdbcc207f58a2a4a6ddb1891d155ded1711', 'bcd6c374fe0d43b8081a7cf2cadb9949018f60a76ea1c1d3dab8a180d3912b07', 'bb7c71b5c08663ba300359b8fe74b9245a7ff613ba1eeb5fcecf031f8e39f9af', '0575b6c0307e88a99d61d4c556eb59bdf117850d6779ce900e977a8828371d38', 'c24af43ecb607a35e5dd0d6082823e1faf869b65c580ba2da8ad694a75d19e9e', '457c41613d4d971801fc95ba371abe011fbc6e8597e54c635e27b31c697adeb3', 'b16f9131aabaa7ac3778e7e3f5d4c5a73bd4963e01bbfe1610ae1fdb38211b63']

LICENSE_FILE = Path.home() / ".keyflow_license"

def is_activated():
    if LICENSE_FILE.exists():
        saved_key = LICENSE_FILE.read_text().strip()
        return hashlib.sha256(saved_key.encode()).hexdigest() in VALID_HASHES
    return False

def activate(key):
    if hashlib.sha256(key.encode()).hexdigest() in VALID_HASHES:
        try:
            LICENSE_FILE.write_text(key)
        except:
            pass
        return True
    return False

class KeyFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KeyFlow Server")
        self.geometry("600x480")
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.url = f"http://{lan_ip()}:{PORT}"
        self.pin = PIN
        
        self.create_tray_icon()
        
        if is_activated():
            self.show_start_screen()
        else:
            self.show_activation_screen()

    def hide_window(self):
        self.withdraw()
        
    def create_tray_icon(self):
        try:
            import pystray
            from PIL import Image
            import threading
            image = Image.open("logo.png")
            menu = pystray.Menu(
                pystray.MenuItem("Show KeyFlow", self.show_window, default=True),
                pystray.MenuItem("Quit", self.quit_app)
            )
            self.tray_icon = pystray.Icon("KeyFlow", image, "KeyFlow", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            pass
            
    def show_window(self, icon, item):
        self.after(0, self.deiconify)
        
    def quit_app(self, icon, item):
        try:
            self.tray_icon.stop()
        except:
            pass
        os._exit(0)

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_activation_screen(self):
        self.clear_window()
        try:
            logo_img = ctk.CTkImage(light_image=Image.open("logo.png"), dark_image=Image.open("logo.png"), size=(80, 80))
            ctk.CTkLabel(self, image=logo_img, text="").pack(pady=(40, 10))
        except:
            pass
        ctk.CTkLabel(self, text="KeyFlow", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(0, 20))
        
        ctk.CTkLabel(self, text="Enter your Product Activation Key:", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
        
        entry = ctk.CTkEntry(self, width=300, font=ctk.CTkFont(size=16), justify="center")
        entry.pack(pady=10)
        
        err_lbl = ctk.CTkLabel(self, text="", text_color="red")
        err_lbl.pack()
        
        def do_activate():
            if activate(entry.get().strip()):
                self.show_start_screen()
            else:
                err_lbl.configure(text="Invalid Activation Key!")
                
        ctk.CTkButton(self, text="Activate", font=ctk.CTkFont(size=16, weight="bold"), command=do_activate).pack(pady=20)
        
        ctk.CTkLabel(self, text="v1.1.0 \u00b7 Secure Mode", font=ctk.CTkFont(size=11), text_color="gray").pack(side="bottom", pady=20)

    def show_start_screen(self):
        self.clear_window()
        try:
            logo_img = ctk.CTkImage(light_image=Image.open("logo.png"), dark_image=Image.open("logo.png"), size=(80, 80))
            ctk.CTkLabel(self, image=logo_img, text="").pack(pady=(60, 10))
        except:
            pass
        ctk.CTkLabel(self, text="Ready to connect", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(0, 30))
        
        def do_start():
            logging.getLogger("werkzeug").setLevel(logging.ERROR)
            Listener(on_press=on_key, daemon=True).start()
            threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": PORT, "threaded": True}, daemon=True).start()
            self.show_qr_screen()
            
        ctk.CTkButton(self, text="Start Server", font=ctk.CTkFont(size=18, weight="bold"), width=200, height=50, command=do_start).pack(pady=20)
        
    def show_qr_screen(self):
        self.clear_window()
        try:
            logo_img = ctk.CTkImage(light_image=Image.open("logo.png"), dark_image=Image.open("logo.png"), size=(64, 64))
            ctk.CTkLabel(self, image=logo_img, text="").pack(pady=(20, 0))
        except:
            pass
        ctk.CTkLabel(self, text="KeyFlow Server", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(10, 5))

        qr = qrcode.QRCode(border=1, box_size=10)
        qr.add_data(f"{self.url}/?pin={self.pin}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        qr_img = ctk.CTkImage(light_image=img.get_image(), dark_image=img.get_image(), size=(220, 220))
        ctk.CTkLabel(self, image=qr_img, text="").pack(pady=15)
        
        ctk.CTkLabel(self, text="Scan to connect or go to:", font=ctk.CTkFont(size=14)).pack()
        ctk.CTkLabel(self, text=self.url, font=ctk.CTkFont(size=16, weight="bold"), text_color="#6cf0cb").pack(pady=(0, 10))

        pin_frame = ctk.CTkFrame(self, corner_radius=10)
        pin_frame.pack(pady=10, padx=60, fill="x")
        ctk.CTkLabel(pin_frame, text="PIN CODE", font=ctk.CTkFont(size=12)).pack(pady=(10, 0))
        ctk.CTkLabel(pin_frame, text=self.pin, font=ctk.CTkFont(size=36, weight="bold", family="Courier")).pack(pady=(0, 10))
        
        ctk.CTkLabel(self, text="Hotkeys: F8 Stop | F9 Pause/Resume", font=ctk.CTkFont(size=12), text_color="gray").pack(side="bottom", pady=20)

if __name__ == "__main__":
    try:
        ui = KeyFlowApp()
        ui.mainloop()
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(f"Failed to start GUI: {e}\n")
