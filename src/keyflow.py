"""
KeyFlow - run this on your PC, control it from your phone on the same Wi-Fi.

Hotkeys on the PC (work globally even while another window has focus):
  F8  stop typing immediately
  F9  pause / resume
"""
import datetime
import functools
import hashlib
import hmac
import logging
import math
import os
import platform
import random
import secrets
import socket
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, request
from pynput.keyboard import Controller, Key, Listener
import customtkinter as ctk
from PIL import Image, ImageDraw
import qrcode

APP_NAME = "KeyFlow"
APP_VERSION = "1.2.0"
APP_BUILD = "2026.10.11-stable"
BASE = Path(__file__).resolve().parent


def resource_path(rel_path: str) -> Path:
    """Resolve resource path across dev, parent dir, and PyInstaller _MEIPASS."""
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / rel_path)
        candidates.append(Path(sys._MEIPASS) / Path(rel_path).name)
    candidates.extend([
        BASE / rel_path,
        BASE.parent / rel_path,
        BASE / "assets" / Path(rel_path).name,
        BASE.parent / "assets" / Path(rel_path).name,
        Path.cwd() / rel_path,
        Path.cwd() / "assets" / Path(rel_path).name,
    ])
    for c in candidates:
        if c.exists():
            return c
    return BASE / rel_path


def load_logo_image(size=(64, 64)) -> Image.Image:
    """Load logo.png or generate a fallback high-contrast icon so it never fails."""
    p = resource_path("assets/logo.png")
    if p.exists():
        try:
            return Image.open(p).convert("RGBA").resize(size, Image.LANCZOS)
        except Exception:
            pass
    img = Image.new("RGBA", size, (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)
    w, h = size
    draw.rounded_rectangle([2, 2, w - 3, h - 3], radius=max(6, w // 5), fill=(88, 28, 135, 255), outline=(168, 85, 247, 255), width=2)
    draw.text((w * 0.30, h * 0.18), "K", fill=(255, 255, 255, 255))
    return img


def find_free_port(start_port: int) -> int:
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


PORT = find_free_port(int(os.environ.get("KEYFLOW_PORT", "8765")))

PIN_FILE = Path.home() / ".keyflow_pin"
if os.environ.get("KEYFLOW_PIN"):
    PIN = os.environ.get("KEYFLOW_PIN")
elif PIN_FILE.exists():
    try:
        PIN = PIN_FILE.read_text().strip()
        if not PIN:
            raise ValueError()
    except Exception:
        PIN = f"{secrets.randbelow(10**6):06d}"
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
<meta name="theme-color" content="#090d1a">
<title>KeyFlow</title>
<style>
:root{
  --text:#f4f7ff; --mute:rgba(226,234,255,.64); --mint:#a855f7; --mint-glow:#c084fc; --mint-ink:#ffffff; --red:#ff6b81; --green:#34d399;
  --glass-bg:linear-gradient(145deg,rgba(255,255,255,.13),rgba(255,255,255,.04));
  --glass-edge:rgba(255,255,255,.16);
  --inner:rgba(255,255,255,.08);
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,Menlo,monospace;
}
*{box-sizing:border-box;margin:0}
html{background:#090d1a;color:var(--text);font:16px/1.45 var(--sans);-webkit-text-size-adjust:100%}
body{min-height:100vh;padding:env(safe-area-inset-top) 0 0}
body::before{content:"";position:fixed;inset:-15%;z-index:-1;background:
  radial-gradient(45% 36% at 15% 15%,rgba(168,85,247,.45),transparent 70%),
  radial-gradient(40% 34% at 88% 22%,rgba(56,189,248,.35),transparent 70%),
  radial-gradient(46% 38% at 24% 86%,rgba(236,72,153,.30),transparent 70%),
  radial-gradient(36% 32% at 90% 88%,rgba(99,102,241,.38),transparent 70%)}
[hidden]{display:none!important}
button,input,textarea{font:inherit;color:inherit}
button{-webkit-tap-highlight-color:transparent}
:focus-visible{outline:2px solid var(--mint-glow);outline-offset:2px}

main{max-width:560px;margin:0 auto;padding:16px 14px calc(140px + env(safe-area-inset-bottom));display:grid;gap:14px}
header{display:flex;align-items:center;justify-content:space-between;padding:4px 4px;gap:10px}
.brand{display:flex;align-items:center;gap:10px}
.brand-badge{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#a855f7,#6366f1);display:grid;place-items:center;font-weight:800;font-size:18px;box-shadow:0 4px 14px rgba(168,85,247,.45)}
h1{font-size:22px;font-weight:800;letter-spacing:-.02em}
.ver{font-size:11px;color:var(--mute);background:rgba(255,255,255,.08);padding:2px 7px;border-radius:99px;border:1px solid rgba(255,255,255,.12)}

.card,.pill,.dock>div,.toast,#login .box{
  position:relative;background:var(--glass-bg);border:1px solid var(--glass-edge);
  -webkit-backdrop-filter:blur(26px) saturate(190%);backdrop-filter:blur(26px) saturate(190%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.28),inset 0 -1px 0 rgba(255,255,255,.05),0 14px 36px rgba(3,6,20,.42)}
.card::before,#login .box::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;
  background:radial-gradient(120% 60% at 10% -10%,rgba(255,255,255,.16),transparent 55%)}
.card{border-radius:26px;padding:16px;overflow:hidden}
.card>*{position:relative}
.card h2{font-size:15px;font-weight:700;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}
.card h2 span{font-size:12px;font-weight:500;color:var(--mute)}
.hint{font-size:13px;color:var(--mute);margin-top:10px;line-height:1.45}
.pill{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--mute);padding:7px 13px;border-radius:99px}
.pill i{width:8px;height:8px;border-radius:50%;background:var(--red);box-shadow:0 0 10px var(--red)}
.pill.on i{background:var(--green);box-shadow:0 0 10px var(--green)}

.gbtn,.chip,.step,.seg{background:var(--inner);border:1px solid rgba(255,255,255,.14);box-shadow:inset 0 1px 0 rgba(255,255,255,.2)}
.gbtn{display:flex;align-items:center;gap:6px;border-radius:99px;padding:7px 12px;font-size:13px;font-weight:600;cursor:pointer;transition:background .15s}
.gbtn svg{width:15px;height:15px;flex:none}
.gbtn:disabled{opacity:.35;cursor:default}
.gbtn:active:not(:disabled){background:rgba(255,255,255,.22)}

/* the tape */
.tape-card{padding:0}
.tools{display:flex;gap:7px;justify-content:space-between;align-items:center;padding:12px 14px 4px;flex-wrap:wrap}
.tools-left{font-size:12px;font-weight:600;color:var(--mute);padding-left:4px}
.tools-right{display:flex;gap:7px}
.tools.off{visibility:hidden}
#text,#tape{display:block;width:100%;height:230px;padding:10px 18px 16px;background:none;border:0;resize:none;
  font:13.5px/1.6 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere;tab-size:4}
#text::placeholder{color:var(--mute)}
#tape{overflow:hidden;display:flex;flex-direction:column;justify-content:center;
  -webkit-mask-image:linear-gradient(transparent 0,#000 18%,#000 82%,transparent 100%);
  mask-image:linear-gradient(transparent 0,#000 18%,#000 82%,transparent 100%)}
#tape .line{white-space:pre-wrap}
#tape .done{color:var(--mute)}
#tape .caret{display:inline-block;width:.6em;height:1.15em;background:var(--mint-glow);vertical-align:text-bottom;
  border-radius:2px;box-shadow:0 0 12px var(--mint-glow);animation:blink 1s steps(2,jump-none) infinite}
.meta{display:flex;justify-content:space-between;gap:12px;padding:10px 18px;font-size:13px;color:var(--mute);border-top:1px solid rgba(255,255,255,.1)}
.bar{height:5px;background:rgba(255,255,255,.08)}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,#a855f7,#38bdf8);box-shadow:0 0 12px var(--mint);transition:width .25s linear}
@keyframes blink{50%{opacity:0}}

/* line breaks: strictly 3 modes sliding glass thumb */
.seg{--i:0;position:relative;display:grid;grid-template-columns:repeat(3,1fr);padding:4px;border-radius:18px}
.seg::before{content:"";position:absolute;top:4px;bottom:4px;left:4px;width:calc((100% - 8px)/3);border-radius:14px;
  transform:translateX(calc(var(--i)*100%));transition:transform .28s cubic-bezier(.3,1.35,.5,1);
  background:linear-gradient(135deg,rgba(168,85,247,.55),rgba(99,102,241,.45));box-shadow:inset 0 1px 0 rgba(255,255,255,.45),0 4px 12px rgba(0,0,0,.3)}
.seg button{position:relative;border:0;background:none;padding:10px 4px;font-size:14px;font-weight:600;border-radius:14px;cursor:pointer}

/* speed */
.speedtop{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px}
.readout{display:flex;align-items:baseline;gap:10px}
.readout b{font-size:44px;line-height:1;font-weight:800;letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.readout span{color:var(--mute);font-size:13px;line-height:1.3}
.nudge{display:flex;gap:8px}
.nudge button{width:44px;height:44px;border-radius:50%;font-size:22px;padding:0;justify-content:center}
input[type=range]{--p:50%;width:100%;height:36px;background:none;-webkit-appearance:none;appearance:none}
input[type=range]::-webkit-slider-runnable-track{height:8px;border-radius:8px;background:linear-gradient(90deg,var(--mint) var(--p),rgba(255,255,255,.16) var(--p))}
input[type=range]::-moz-range-track{height:8px;border-radius:8px;background:rgba(255,255,255,.16)}
input[type=range]::-moz-range-progress{height:8px;border-radius:8px;background:var(--mint)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:28px;height:28px;margin-top:-10px;border-radius:50%;
  background:linear-gradient(#fff,#dfe8f5);border:0;box-shadow:0 3px 10px rgba(0,0,0,.4),inset 0 1px 0 #fff}
input[type=range]::-moz-range-thumb{width:28px;height:28px;border-radius:50%;background:#eef3fb;border:0;box-shadow:0 3px 10px rgba(0,0,0,.4)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}
.chip{padding:8px 14px;border-radius:99px;font-size:13.5px;font-weight:600;cursor:pointer}
.chip[aria-pressed=true]{background:var(--mint);color:var(--mint-ink);border-color:transparent;box-shadow:0 4px 14px rgba(168,85,247,.4)}

/* rows */
.row{display:flex;align-items:center;justify-content:space-between;gap:12px}
.sep{margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.12)}
.row b{display:block;font-size:15px;font-weight:600}
.row small{color:var(--mute);font-size:13px}
.switch{position:relative;width:52px;height:30px;flex:none}
.switch input{opacity:0;width:0;height:0}
.switch span{position:absolute;inset:0;border-radius:99px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.2);cursor:pointer;transition:.2s}
.switch span::before{content:"";position:absolute;width:24px;height:24px;left:3px;top:2px;border-radius:50%;background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.35);transition:.22s cubic-bezier(.3,1.35,.5,1)}
.switch input:checked + span{background:var(--mint)}
.switch input:checked + span::before{transform:translateX(20px)}
.switch input:focus-visible + span{outline:2px solid var(--mint);outline-offset:2px}
.step{display:flex;align-items:center;border-radius:99px;overflow:hidden}
.step button{border:0;background:none;width:42px;height:38px;font-size:20px;cursor:pointer}
.step output{min-width:44px;text-align:center;font-weight:600;font-variant-numeric:tabular-nums}

/* snippets */
details summary{cursor:pointer;font-weight:600;font-size:15px;list-style:none;display:flex;justify-content:space-between;align-items:center}
details summary::-webkit-details-marker{display:none}
details summary::after{content:"+";font-size:20px;color:var(--mute)}
details[open] summary::after{content:"\2212"}
.snips{display:grid;gap:8px;margin-top:12px}
.snip{display:flex;gap:8px}
.snip button{border:1px solid rgba(255,255,255,.14);background:var(--inner);border-radius:14px;cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.2)}
.snip button:first-child{flex:1;text-align:left;padding:12px 14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.snip button:last-child{width:46px;color:var(--mute)}
.link{background:none;border:0;color:var(--mint-glow);padding:12px 0 0;font-size:14px;font-weight:600;cursor:pointer}
.forget{justify-self:center;background:none;border:0;color:var(--mute);font-size:13px;padding:6px;cursor:pointer;text-decoration:underline;text-underline-offset:3px}

/* dock + toast */
.dock{position:fixed;left:12px;right:12px;bottom:calc(10px + env(safe-area-inset-bottom))}
.dock>div{max-width:536px;margin:0 auto;padding:8px;display:flex;gap:8px;border-radius:32px}
.btn{flex:1;min-height:56px;border:0;border-radius:24px;font-weight:700;font-size:17px;cursor:pointer;transition:transform .12s}
.btn:active{transform:scale(.97)}
.btn.go{background:linear-gradient(135deg,#c084fc,#a855f7,#6366f1);color:var(--mint-ink);box-shadow:inset 0 1px 0 rgba(255,255,255,.55),0 6px 20px rgba(168,85,247,.4)}
.btn.go:disabled{opacity:.6}
.btn.stop{flex:0 0 104px;background:rgba(255,107,129,.18);border:1px solid rgba(255,107,129,.4);color:var(--red)}
.toast{position:fixed;left:50%;bottom:calc(98px + env(safe-area-inset-bottom));z-index:5;display:flex;align-items:center;gap:14px;
  padding:11px 12px 11px 18px;border-radius:99px;font-size:14px;white-space:nowrap;max-width:calc(100vw - 24px);
  opacity:0;transform:translate(-50%,16px);pointer-events:none;transition:opacity .2s,transform .25s cubic-bezier(.3,1.35,.5,1)}
.toast.show{opacity:1;transform:translate(-50%,0);pointer-events:auto}
.toast button{border:0;background:rgba(255,255,255,.18);color:var(--mint-glow);font-weight:600;border-radius:99px;padding:7px 14px;cursor:pointer}
.toast span{overflow:hidden;text-overflow:ellipsis}

/* login */
#login{min-height:100vh;display:grid;place-items:center;padding:20px}
#login .box{width:100%;max-width:360px;border-radius:28px;padding:24px;display:grid;gap:14px;text-align:center}
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
    <div class="brand" style="justify-content:center">
      <div class="brand-badge">K</div>
      <h1>KeyFlow</h1>
    </div>
    <p>Enter the 6-digit PIN shown on the KeyFlow PC dashboard.</p>
    <input id="pin" inputmode="numeric" autocomplete="off" maxlength="12" aria-label="PIN">
    <div class="err" id="loginErr"></div>
    <button class="btn go" id="connect">Connect to PC</button>
  </div>
</section>

<main id="app" hidden>
  <header>
    <div class="brand">
      <div class="brand-badge">K</div>
      <h1>KeyFlow</h1>
      <span class="ver">v1.2</span>
    </div>
    <div class="pill" id="pill"><i></i><span>Connecting</span></div>
  </header>

  <section class="card tape-card" aria-label="Text to type">
    <div class="tools" id="tools">
      <span class="tools-left" id="activeModeTag">MODE: CODE</span>
      <div class="tools-right">
        <button class="gbtn" id="paste"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4h6v3H9z"/></svg>Paste</button>
        <button class="gbtn" id="cleanIndent" title="Convert tabs to 4 spaces & trim trailing spaces">Clean</button>
        <button class="gbtn" id="clear"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>Clear</button>
      </div>
    </div>
    <textarea id="text" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off"
      placeholder="Paste or write code / text for your PC to type..."></textarea>
    <div id="tape" hidden aria-live="off"></div>
    <div class="meta"><span id="count">0 characters · 0 lines</span><span id="note"></span></div>
    <div class="bar"><i id="fill"></i></div>
  </section>

  <section class="card">
    <h2>Typing Mode <span>3 Modes</span></h2>
    <div class="seg" id="seg"></div>
    <p class="hint" id="modeHint"></p>
    <div class="row sep">
      <div><b>Start delay</b><small>Time to focus target window on PC</small></div>
      <div class="step"><button id="dMinus" aria-label="Shorter delay">&minus;</button><output id="delay">5 s</output><button id="dPlus" aria-label="Longer delay">+</button></div>
    </div>
  </section>

  <section class="card">
    <h2>Speed <span>Auto-Indent Safe</span></h2>
    <div class="speedtop">
      <div class="readout"><b id="cps">14</b><span>characters / sec<br>~<span id="wpm">168</span> WPM</span></div>
      <div class="nudge">
        <button class="gbtn" id="slower" aria-label="Slower">&minus;</button>
        <button class="gbtn" id="faster" aria-label="Faster">+</button>
      </div>
    </div>
    <input type="range" id="speed" min="0" max="100" step="1" aria-label="Typing speed">
    <div class="chips" id="chips"></div>
    <div class="row sep">
      <div><b>Human rhythm</b><small>Natural micro-variations between keys</small></div>
      <label class="switch"><input type="checkbox" id="human" aria-label="Human rhythm"><span></span></label>
    </div>
  </section>

  <section class="card">
    <details>
      <summary>Saved snippets</summary>
      <div class="snips" id="snips"></div>
      <button class="link" id="save">+ Save current text as snippet</button>
    </details>
  </section>

  <button class="forget" id="forget">Disconnect & forget PIN on this phone</button>
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
  code:  ["Code",        "Smart Auto-Indent Mode: Dismisses IDE popups, cleans auto-closed brackets, and resets each new line to Column 0 so your exact code indentation is preserved at any speed."],
  shift: ["Shift+Enter", "Chat Mode: Presses Shift+Enter for line breaks without sending the message (WhatsApp, Discord, Slack, Teams)."],
  enter: ["Enter",       "Standard Mode: Presses plain Enter at every line break. Best for Notepad, Word, and plain text editors."]
};
const PRESETS = [["Slow",5],["Natural",14],["Fast",45],["Turbo",120]];
const KEY = "keyflow:v2", SKEY = "keyflow:snips";

const cpsOf = v => Math.max(1, Math.round(Math.pow(160, v / 100)));
const vOf = c => Math.round(100 * Math.log(Math.max(1, c)) / Math.log(160));
const clampC = c => Math.min(160, Math.max(1, Math.round(c)));
const stepOf = c => c < 20 ? 1 : c < 60 ? 5 : 10;

let saved = {}; try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
let S = Object.assign({text:"", cps:14, mode:"code", human:false, delay:5}, saved);
if (!MODES[S.mode]) S.mode = "code";
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
$("#cleanIndent").onclick = () => {
  if (!S.text) return toast("Nothing to clean");
  const old = S.text;
  const cleaned = S.text.replace(/\r\n?/g, "\n").replace(/\t/g, "    ").split("\n").map(l => l.replace(/[ \t]+$/, "")).join("\n");
  setText(cleaned);
  toast("Tabs converted & trailing spaces cleaned", "Undo", () => setText(old));
};
$("#paste").onclick = async () => {
  try {
    const t = await navigator.clipboard.readText();
    if (!t) return toast("Clipboard is empty");
    const old = S.text; setText(t);
    toast("Pasted from clipboard", old ? "Undo" : null, () => setText(old));
  } catch (e) {
    $("#text").focus();
    toast("Long-press inside the box and tap Paste");
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
  b.className = "chip"; b.dataset.c = c; b.textContent = name + " · " + c;
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
  if (!MODES[S.mode]) S.mode = "code";
  document.querySelectorAll("#seg button").forEach(b => b.setAttribute("aria-pressed", b.dataset.k === S.mode));
  $("#seg").style.setProperty("--i", Object.keys(MODES).indexOf(S.mode));
  $("#modeHint").textContent = MODES[S.mode][1];
  $("#activeModeTag").textContent = "MODE: " + MODES[S.mode][0].toUpperCase();
  drawMeta();
}
$("#human").onchange = e => { S.human = e.target.checked; save(); };
const drawDelay = () => $("#delay").textContent = S.delay + " s";
$("#dMinus").onclick = () => { S.delay = Math.max(0, S.delay - 1); save(); drawDelay(); };
$("#dPlus").onclick  = () => { S.delay = Math.min(30, S.delay + 1); save(); drawDelay(); };

function norm(t) {
  return t.replace(/\r\n?/g, "\n");
}
function drawMeta() {
  $("#clear").disabled = !S.text;
  $("#cleanIndent").disabled = !S.text;
  if (busy()) return;
  const t = S.text, n = Array.from(norm(t)).length;
  const lines = t ? t.split(/\r\n|\r|\n/).length : 0;
  $("#count").textContent = n.toLocaleString() + " characters \u00b7 " + lines + " lines";
  $("#note").textContent = n ? "est. " + fmt(n / S.cps + (S.mode === "code" ? lines * 0.35 : 0)) : "";
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
  if (st.state === "countdown") {
    go.textContent = "Starting in " + st.countdown + "s\u2026";
    go.disabled = true;
    $("#count").textContent = "Click into your target window on PC";
    $("#note").textContent = "Countdown";
    drawTape();
  } else if (st.state === "typing" || st.state === "paused") {
    go.textContent = st.state === "paused" ? "Resume typing" : "Pause";
    $("#count").textContent = st.typed.toLocaleString() + " / " + st.total.toLocaleString() + (st.state === "paused" ? " \u00b7 PAUSED" : "");
    const left = (st.total - st.typed) / Math.max(1, st.cps || S.cps);
    $("#note").textContent = st.state === "paused" ? "F9 or tap Resume" : fmt(left) + " left";
    drawTape();
  } else {
    go.textContent = st.state === "done" || st.state === "stopped" ? "Type again" : "Start typing";
    if (st.state === "done") { $("#count").textContent = "Completed \u00b7 " + st.total.toLocaleString() + " characters typed"; $("#note").textContent = "100%"; }
    else if (st.state === "stopped") { $("#count").textContent = "Stopped at " + st.typed.toLocaleString() + " of " + st.total.toLocaleString(); $("#note").textContent = ""; }
    else drawMeta();
  }
}

async function poll() {
  if (!PIN) return showLogin();
  try {
    const prev = st.state;
    st = await api("status");
    $("#pill").className = "pill on";
    $("#pill span").textContent = st.host + " \u00b7 " + st.state.toUpperCase();
    $("#app").hidden = false; $("#dock").hidden = false; $("#login").hidden = true;
    if (prev !== st.state && (st.state === "done" || st.state === "stopped")) navigator.vibrate && navigator.vibrate(120);
    render();
  } catch (e) {
    if (e.message === "auth") return;
    $("#pill").className = "pill"; $("#pill span").textContent = "PC offline";
    $("#app").hidden = false;
  }
}

$("#text").value = S.text; $("#human").checked = S.human;
drawSpeed(); drawMode(); drawDelay(); drawSnips();
poll(); setInterval(poll, 300);
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
job = {
    "state": "idle",
    "typed": 0,
    "total": 0,
    "cps": 14.0,
    "countdown": 0,
    "mode": "code",
}
fails = {}  # ip -> [failed_count, locked_until]
event_logs = []


def add_log(msg: str):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    event_logs.append(entry)
    if len(event_logs) > 200:
        del event_logs[: len(event_logs) - 200]


# ----------------------------------------------------------------- typing ---
def tap_key(key, delay_after=0.012):
    kb.press(key)
    time.sleep(0.01)
    kb.release(key)
    if delay_after > 0:
        time.sleep(delay_after)


def shift_tap(key, delay_after=0.018):
    kb.press(Key.shift)
    time.sleep(0.012)
    kb.press(key)
    time.sleep(0.015)
    kb.release(key)
    time.sleep(0.012)
    kb.release(Key.shift)
    if delay_after > 0:
        time.sleep(delay_after)


def press_newline(mode: str):
    """
    Insert a line break according to one of the 3 modes:
      - 'shift': Shift+Enter (chat apps without sending)
      - 'enter': Plain Enter
      - 'code':  Smart Auto-Indent aware newline:
                 1) Dismisses any open IDE autocomplete/IntelliSense popup AND
                    cleans any auto-closed brackets/parens/quotes to the right of
                    the cursor via Shift+End -> Space -> Backspace.
                 2) Presses Enter and waits for the IDE's auto-indent to settle.
                 3) Clears all auto-indentation on the new line via
                    Space -> Shift+Home -> Backspace so the cursor is guaranteed
                    to start at Column 0 before typing the line's exact spaces.
    """
    if mode == "shift":
        shift_tap(Key.enter, delay_after=0.02)
        return
    if mode == "enter":
        tap_key(Key.enter, delay_after=0.02)
        return

    # mode == "code"
    time.sleep(0.03)
    # Step 1: Select any auto-closed characters to the right of cursor, overwrite
    # with a space (which also closes any open IntelliSense popup), then delete space.
    shift_tap(Key.end, delay_after=0.015)
    tap_key(Key.space, delay_after=0.015)
    tap_key(Key.backspace, delay_after=0.02)

    # Step 2: Press Enter and wait for IDE auto-indent / language server
    tap_key(Key.enter, delay_after=0.09)

    # Step 3: Clear new line's auto-indentation back to Column 0
    tap_key(Key.space, delay_after=0.018)
    shift_tap(Key.home, delay_after=0.025)
    tap_key(Key.backspace, delay_after=0.025)


def type_char(ch: str, mode: str):
    try:
        if mode == "code" and ch == "\t":
            # Type 4 spaces instead of Tab key so IDE autocomplete/snippets aren't triggered
            for _ in range(4):
                kb.type(" ")
                time.sleep(0.01)
        else:
            kb.type(ch)
    except Exception:
        pass


def finish(state: str):
    job["state"] = state
    job["countdown"] = 0
    pause_evt.clear()
    add_log(f"Typing job {state} ({job['typed']:,} / {job['total']:,} chars).")


def run_job(text: str, mode: str, humanize: bool, delay: int):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    n = len(text)
    job["total"] = n
    job["mode"] = mode

    add_log(f"Starting job: {n:,} chars, mode={mode.upper()}, speed={job['cps']:.0f} CPS, delay={delay}s.")

    for s in range(delay, 0, -1):
        job["countdown"] = s
        if stop_evt.wait(1):
            return finish("stopped")
    job["countdown"] = 0
    job["state"] = "typing"

    i = 0
    at_line_indent = True  # True while we are in the leading whitespace of the current line

    # If the very first line in code mode is blank whitespace before \n, skip its trailing spaces
    if mode == "code":
        nl_pos = text.find("\n")
        if nl_pos != -1 and text[:nl_pos].strip(" \t") == "":
            i = nl_pos

    next_t = time.perf_counter()

    while i < n:
        if stop_evt.is_set():
            return finish("stopped")
        if pause_evt.is_set():
            job["state"] = "paused"
            add_log("Typing paused.")
            while pause_evt.is_set() and not stop_evt.is_set():
                stop_evt.wait(0.1)
            if stop_evt.is_set():
                return finish("stopped")
            job["state"] = "typing"
            add_log("Typing resumed.")
            next_t = time.perf_counter()

        cps = max(1.0, float(job["cps"]))
        ch = text[i]

        if ch == "\n":
            press_newline(mode)
            i += 1
            at_line_indent = True
            # In code mode, if the new line is purely whitespace before the next \n,
            # skip typing useless spaces on the blank line while keeping progress synced.
            if mode == "code" and i < n:
                nl_pos = text.find("\n", i)
                if nl_pos != -1 and text[i:nl_pos].strip(" \t") == "":
                    i = nl_pos
                elif nl_pos == -1 and text[i:].strip(" \t") == "":
                    i = n
            job["typed"] = i
            # CRITICAL: Reset next_t after newline so we NEVER sprint to "catch up"
            next_t = time.perf_counter()
            continue

        # Check if we are still in leading indentation
        if at_line_indent and ch not in (" ", "\t"):
            at_line_indent = False

        type_char(ch, mode)
        i += 1
        job["typed"] = i

        # Calculate safe inter-character delay
        gap = 1.0 / cps
        if mode == "code":
            if at_line_indent:
                # Guarantee at least 12ms per leading indentation space so IDEs
                # never drop indentation spaces even at Turbo speeds.
                gap = max(gap, 0.012)
            else:
                # Guarantee at least 7ms between code chars so OS buffer never overflows
                gap = max(gap, 0.007)
        else:
            gap = max(gap, 0.005)

        if humanize:
            gap *= random.uniform(0.55, 1.55)
            if ch == " " and random.random() < 0.10:
                gap += random.uniform(0.05, 0.18)

        next_t += gap
        now = time.perf_counter()
        wait = next_t - now
        if wait > 0:
            stop_evt.wait(wait)
        else:
            # Never accumulate negative lag debt that causes zero-delay bursts
            next_t = now

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
    return jsonify(**job, host=socket.gethostname(), version=APP_VERSION)


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
        cps = min(200.0, max(1.0, float(data.get("cps", 14))))
        delay = min(60, max(0, int(data.get("delay", 5))))
    except (TypeError, ValueError):
        return jsonify(error="Invalid speed or delay."), 400

    with lock:
        if worker and worker.is_alive():
            return jsonify(error="Already typing."), 409
        stop_evt.clear()
        pause_evt.clear()
        norm_text = text.replace("\r\n", "\n").replace("\r", "\n")
        job.update(
            state="countdown",
            typed=0,
            total=len(norm_text),
            cps=cps,
            countdown=delay,
            mode=mode,
        )
        worker = threading.Thread(
            target=run_job,
            args=(norm_text, mode, bool(data.get("humanize")), delay),
            daemon=True,
        )
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
        job["cps"] = min(200.0, max(1.0, float(data.get("cps", job["cps"]))))
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
        if job["state"] in ("countdown", "typing", "paused"):
            add_log("Hotkey F8 pressed: Emergency Stop.")
            stop_evt.set()
    elif key == Key.f9:
        if job["state"] in ("typing", "paused"):
            add_log("Hotkey F9 pressed: Toggle Pause/Resume.")
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


VALID_HASHES = [
    '5e6b6f29d459986dd2c83bc69a0b4a6b6c63c8e824602b2826627311d1234ad5', 'a241c8487db829015fbb518bc0a31799a5482ac47d8a3db0f081bc407e255ee3',
    'fb4449e78636a1f23c171fd7a0b875ee30e6e0085db5c1fbdcc8d65965b322a0', '9cc276a89369fb9facd74d67c05a5b97412564fc3e4c62194708e8708e9670ce',
    '981117b12658df79beaf6276ffaa259c9fc308f631a0637fe865f165a96f26a9', 'a0c9d01e5db4c782c3e65b6b65162e8908bd974f35c39ae665d8abcf10a00a85',
    'd7ebf7604fc5cffbb89765984684c50316d128890653cfb2cb6141eb4dfc68cb', 'c852aa196ea9ada9393f4f36ff5c620886abe30dda542fe5e5460fec2a508850',
    'b493292fc12d0c70c740a878c3564a7165fc4bce4734e57e0dcbc6ec09571c19', '8b1d7597d31db5f42aa19b51b089789da2d27b796eb053a86adaaaaa4ea451df',
    '244a11ec752bc079f8a3a71589a9fad9b64065582ba27c1be24427c0e70bfbcf', '1139c29314f800d7f2234bcbd48223691bb9113a3ec5630387116620dccf5b96',
    '2268bf7e8322b338a5f15bc9eb7ae5d1a7fa84c038015c8957de6daedd6ce4a9', 'dedf8d2165a6df2798733611d8fb9fe171d5977eb5bfb8b4d6c1da035f093efc',
    '4843e65de2fb4f377812422412ce3774abce9fe600bde051ee8eaf4fdd63d288', '0406670a8d46a88ca3a7f20f85ed7a827d6591ea42e9cdf948a9384f4bd34538',
    'cb1b5de2f2d4e9775f219a79667dc90f558c4a61a1a7b566784a92817dc1bc16', '1dc8b60fe01095c0af88d96721525a3f931b18f2356b79c790e8eb6caf0ac098',
    '9ea02b98ea6bc2609042376a129013c27a3b6ea84f835984f300ffd35abb87b3', '81db9692680f3de40b2085ffc1b7d7a345d847a233405bab72da89ed8b864444',
    '0de24ba6409d13f01b50874c38d3b24c5e742abdd5fc0e7878b4175a4c38b61b', 'bfb070f135c1a5014f7e5c8c670f575dda0e731bcd9841001ec81cf2d8f7ba12',
    'f570a00ab9fdd3063ccbdfa2bc53a3af3184a922f643fc6e93b697a5bf7bb6e8', '2f66007fc7ddc6e153cbad7f851c7cabc8f1c9e5b5826c597b42213484feffea',
    'a88c5c03523d550645c8c48fe31bd51a244756dd4ece4ec5cefc5c9c0b009357', '9b34b8fbecf27ac3d7bee4c9747dd13c6fe1d9acf7fe7885434c09b1cb0c614b',
    '39a340e0cca4d2b6eb5ce6630011a88826a348fa9f6b0ce688008d76b2e1b9a4', '563b5b501d4f114dbc6d9f478a7e41e6bdaf0a3eaf0014f829df888790c514e3',
    '71c20c155565b29c20a6983f73136deabd858915680b2afaaf8648b9d771c329', 'f4f36dc045a62fb41b912c98469698afed33ca3e03f97400932efc142c52ff5e',
    'a1ad8e98b6f266204667c1e1c1c67971025d1845fbeeff716e73045c5edd9f7a', 'c7050f51a252704f4cb9c4d1658660e8c2b667b55514c7a9ad6d09ecb08b7376',
    '21f4f64494cdaa4d5974af8081056dc50eeecc7fbe0ae65ab72804f7e63fb6f5', 'eb9d89930ef0d052ea6f4b233ebb0c1770c611814a8d458af68fe5d1a01ecddc',
    '8fd209be5754d155007fc33379e47cf7d7426470c4f81c5d1bb76800d065e785', 'bcdb69c886a457a7abbcd9b08009b4930e5a2da2745066e6db1d9e535905903b',
    '2c3abe5fb3c97a5a304a571a749e2b286abc29c19b49dd3b04a90b6971565544', '42004d5d44874c3f2ba2c84d097187e797a08a616f41c84315e4572108305067',
    'c113bfd96ddd4a036ca37ead1d4f69e04828f746dd47b5933f56fb5c158ca1d8', 'd22d8fb304065ee67eedf70a611bbfd7154cc5a9f37bfa125608836d154064e4',
    'f4277108ca32500465cd44a5f23e231e03fcde5779a5720eb6368b2e86b31661', 'cc63152169282514e6a973c3d4bd7b3dbe71c5d549bc2a7339128927593517a1',
    'f0c9c188504e7e17d77403d982e681c281c085b6eedd0f8f04c63e873daa0baf', 'af34d6c2161750527fd3c112cb1d9a610edf9169cbdc239c7124bea7c440738c',
    'ff73234f9a455b61f435c1b9f0150820425fb414bca7f0dc6741b574fe1b3a71', 'c90c17672e89616488b41753c450a7d165a78d9b25fae67944b603e29fa4e163',
    'f1dbc5989b75136637df2ed303e90035eb0c99943d17ce90391485dc37584a9e', 'f1b42181ad2d508a3b39750df753c50cc26ceea0f0224f933ce02e37d831a516',
    '85da68525723d59165be5e9e8086d8247a4898c844f39b9b096a646600aed976', '08370559861034f4ee2d32b375b552af76b95aa334f3e72983a4c67dffe576ce',
    'acfb8c501f4fb8ec4d6805032ffacf81d4155cd5a957a5539f12db338f007581', '1debfcef84b01944ee93f6a05b4609b119b86e360385920793e898b04a00b5ff',
    'e98ca2a33cbfc10322a9fca2c715c40e19e8ccfedc5614dcb08577ea1bc72cc8', 'b39d74fd6e1eed6c07922ba9bee77b5646fea1fe431ce16e005996744e662e63',
    'c09d7772eeb1441fe4628f03a23a87f370009bfd9a196cd7fd6183516735f346', '4cd61f63f9c8422fe1a463cf415b454ceb0a20230680248d0c7428e2215d45c9',
    'e400a0f3b6b48d732c27439ab40b8e11a0ba5704a09e8bd579a51d8ac7ac4358', 'c858ba451041f0bea907342db1103cbd148412450ee4f51e8106f3d37ca5c675',
    '9d1b2962de415fbf07717c080a3d17c9fe049df2c894ec1e2313069d15b48370', '041a95d5f19007e4c3cb041de38533ae6f6cb8a9996a5a118de00ad7c5114bb4',
    'b6aca1e017c7f8dd13457cca725f6268cb0c20b68860b9a7e7fd7d1de0f3cdf1', '561212d834f981f26a5770b0757d2fb027594dcd0d241d4bceb96071cc1d29f4',
    '6003510f855fdebee0c9b146ee1c45648558045cdf4021be021df136c7c2930f', '45c7c5798f13e464c094bd17ad067a2adb33290eef08a40b83e9d89a636bfc27',
    'e2e40d752287254af080af426a0c2627ee1ad7ba6cb83cac1b82bdc957862c0a', 'ada19e2f396eae89ea54a45097f0445c47216edf11f9a8ac1de9d436a1cec4d2',
    '0cf3919bab235f2eea7c63698d45c893bc1dadfb91cd9e4df111e638db48b617', '0803734a2741aac616e9fc5892ccdc5a51cb817d2e47adcc013ae78a69cafcd6',
    '39a9948e778868d26967eab796d6e01c1923a5fb7c1e079de318238666f00ec8', '1b9c63f955d198ad827b855052727e0a940f12182e451a9dec1af54284eccdc3',
    '64470e22d462057fe7440c0304985d5775154085c916628b19f61dcc2344fada', '2ad2d5c3a6c7d359f6d846b160fa054f8d6bc1cc3a750547790b193493716c0d',
    'dc78b6710f78312f9efac67a3fb4aa7f269451e17befbbf7bc94216b377759b0', '545ed06ae3a377efd1c257b7174fc9783fd68b056b7bbb5567af4f394b5f89b4',
    '8fedb5dee88c5e9b46442e84b058933e3acaeef80e5680a306b4dfca3d595a9c', '8be12cac25ecfd214016cf02c7505a04fabb0f3863beb0545c2a88fe40266e8b',
    'b7a9ff4ccacc144a4c70cc9b2d0b23369e0792a09fcee46a8458a1b026a5d01a', 'b31fcd160ce16eb758d8b878b8186ad74b97ca80058b6d709be211db48dc35da',
    'f150b6622552aecc12b424dd9ac1ca9d66d637a5e8a010caf36ca199285dc91e', '1fe7b368a4b15f83cf79ae71f54db4160351a6fc3ff28e4d70502a055fc01418',
    '568a1a1d859943c2457ad675e2c25b321c7eaf375bd7b08ac0d4fccb4e209479', '6c45e736ef54b4ee77af270ed0e14d30817496fb1b5d892ea74eadf435ba0c4e',
    '66f3f500ba7edd52d0d9302af89956afe87e403ecdcb19fdedcd034590772ddb', '17136c6d7dfcd2a3f30e55848dd6c21d73ab283e532877030a7c7942eda2ff58',
    'f3bdd61205a74e0e38516c060ce3a162ecde95f98371388ad413e25833836443', 'f3aa61d304f473788843429b4f149d3cb9d223bd5de121acfca8ad275d551cd8',
    '0a01dc6e687f3b7a65385550597c370a4ef2de21aac3fb051db8885c016749ba', '3befa63f414d13e75339f1b38928d730313958508eb82ad9d4e4b13b3c0d34a4',
    '790cb0900526dc6c5b7f039704cecb66c6824299935740000822750641e5a486', '61a7718bf60c6c34d00f4dcca732a9b37404c85229a03dc8e838483c73f77e20',
    '2d42c146ba930d67d2858e4dc8622b12804771f074ab25270a570041a38decda', 'bf3359bd0c1ac970d8781f4982e78106810e7f179316af1cf439c2194ffabd53',
    '21f7f58cc3319ae58d9901ea4bd57b320c86755f030460dbc733e1de8f3ab565', 'd3c52c65b064c6fa78ac8f7daed7bcdbcc207f58a2a4a6ddb1891d155ded1711',
    'bcd6c374fe0d43b8081a7cf2cadb9949018f60a76ea1c1d3dab8a180d3912b07', 'bb7c71b5c08663ba300359b8fe74b9245a7ff613ba1eeb5fcecf031f8e39f9af',
    '0575b6c0307e88a99d61d4c556eb59bdf117850d6779ce900e977a8828371d38', 'c24af43ecb607a35e5dd0d6082823e1faf869b65c580ba2da8ad694a75d19e9e',
    '457c41613d4d971801fc95ba371abe011fbc6e8597e54c635e27b31c697adeb3', 'b16f9131aabaa7ac3778e7e3f5d4c5a73bd4963e01bbfe1610ae1fdb38211b63'
]

LICENSE_FILE = Path.home() / ".keyflow_license"


def is_activated() -> bool:
    if LICENSE_FILE.exists():
        try:
            saved_key = LICENSE_FILE.read_text().strip()
            return hashlib.sha256(saved_key.encode()).hexdigest() in VALID_HASHES
        except Exception:
            return False
    return False


def activate(key: str) -> bool:
    if hashlib.sha256(key.encode()).hexdigest() in VALID_HASHES:
        try:
            LICENSE_FILE.write_text(key)
        except Exception:
            pass
        return True
    return False


# ----------------------------------------------------------- Desktop GUI ---
class KeyFlowApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} Desktop Server — v{APP_VERSION}")
        self.geometry("960x650")
        self.minsize(800, 560)
        self.resizable(True, True)

        # Center window on screen
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - 960) // 2)
        y = max(0, (sh - 650) // 2)
        self.geometry(f"960x650+{x}+{y}")

        # Set window icon if available
        ico_path = resource_path("assets/logo.ico")
        if ico_path.exists():
            try:
                self.iconbitmap(str(ico_path))
            except Exception:
                pass

        self.close_to_tray = tk.BooleanVar(value=True)
        self.always_on_top = tk.BooleanVar(value=False)
        self.server_started = False
        self.qr_size_mode = "normal"  # "normal" or "large"
        self._last_log_len = 0

        self.url = f"http://{lan_ip()}:{PORT}"
        self.pin = PIN

        self.protocol("WM_DELETE_WINDOW", self.on_close_button)
        self.bind("<Control-m>", lambda e: self.hide_window())
        self.bind("<Control-q>", lambda e: self.quit_app())

        self.create_tray_icon()

        if is_activated():
            self.start_backend_server()
            self.build_main_interface()
        else:
            self.show_activation_screen()

    # -------------------- System Tray & Window Lifecycle --------------------
    def create_tray_icon(self):
        try:
            import pystray
            image = load_logo_image((64, 64))
            menu = pystray.Menu(
                pystray.MenuItem("Open KeyFlow Dashboard", self.show_window_from_tray, default=True),
                pystray.MenuItem("Pause / Resume Typing (F9)", lambda icon, item: toggle_pause()),
                pystray.MenuItem("Emergency Stop (F8)", lambda icon, item: stop_evt.set()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit KeyFlow Completely", self.quit_app),
            )
            self.tray_icon = pystray.Icon("KeyFlow", image, f"KeyFlow Server ({self.url})", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            add_log(f"Tray initialization note: {e}")

    def on_close_button(self):
        if self.close_to_tray.get():
            self.hide_window()
        else:
            self.quit_app()

    def hide_window(self):
        add_log("Window minimized to system tray (running in background).")
        self.withdraw()

    def show_window_from_tray(self, icon=None, item=None):
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self, icon=None, item=None):
        stop_evt.set()
        try:
            if hasattr(self, "tray_icon"):
                self.tray_icon.stop()
        except Exception:
            pass
        os._exit(0)

    def start_backend_server(self):
        if self.server_started:
            return
        self.server_started = True
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        Listener(on_press=on_key, daemon=True).start()
        threading.Thread(
            target=app.run,
            kwargs={"host": "0.0.0.0", "port": PORT, "threaded": True},
            daemon=True,
        ).start()
        add_log(f"Server online at {self.url} (Host: {socket.gethostname()})")

    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()

    # -------------------- Activation Screen --------------------
    def show_activation_screen(self):
        self.clear_window()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        wrapper = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0)
        wrapper.grid(row=0, column=0, sticky="nsew")
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(wrapper, width=460, corner_radius=20, fg_color="#1e293b", border_width=1, border_color="#334155")
        card.grid(row=0, column=0, padx=24, pady=24)

        logo_pil = load_logo_image((76, 76))
        logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(76, 76))
        ctk.CTkLabel(card, image=logo_ctk, text="").pack(pady=(32, 10))

        ctk.CTkLabel(card, text="KeyFlow Desktop", font=ctk.CTkFont(size=26, weight="bold"), text_color="#f8fafc").pack(pady=(0, 4))
        ctk.CTkLabel(card, text="Enter your Product Activation Key to unlock KeyFlow", font=ctk.CTkFont(size=13), text_color="#94a3b8").pack(pady=(0, 20), padx=36)

        entry = ctk.CTkEntry(
            card,
            width=340,
            height=44,
            placeholder_text="XXXX-XXXX-XXXX-XXXX",
            font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
            justify="center",
            fg_color="#0f172a",
            border_color="#475569",
        )
        entry.pack(pady=6, padx=36)

        err_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=13), text_color="#fb7185")
        err_lbl.pack(pady=4)

        def do_activate():
            if activate(entry.get().strip()):
                add_log("Product license activated successfully.")
                self.start_backend_server()
                self.build_main_interface()
            else:
                err_lbl.configure(text="Invalid Activation Key. Please check and try again.")

        entry.bind("<Return>", lambda e: do_activate())

        ctk.CTkButton(
            card,
            text="Activate KeyFlow",
            width=340,
            height=44,
            corner_radius=12,
            fg_color="#9333ea",
            hover_color="#7e22ce",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=do_activate,
        ).pack(pady=(10, 24), padx=36)

        ctk.CTkLabel(
            card,
            text=f"v{APP_VERSION} · Build {APP_BUILD} · SHA-256 Verified",
            font=ctk.CTkFont(size=11),
            text_color="#64748b",
        ).pack(pady=(0, 20))

    # -------------------- Main Desktop Application UI --------------------
    def build_main_interface(self):
        self.clear_window()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top Menu Bar
        self.grid_rowconfigure(1, weight=1)  # Main Content Area
        self.grid_rowconfigure(2, weight=0)  # Bottom Status Bar

        self._build_top_menubar()
        self._build_dashboard_body()
        self._build_status_bar()

        self._poll_ui_status()

    def _build_top_menubar(self):
        """Builds a sleek dark desktop menu bar (File | View | Settings | Build Info) + right-side quick tray button."""
        menubar = ctk.CTkFrame(self, height=42, corner_radius=0, fg_color="#090d16", border_width=1, border_color="#1e293b")
        menubar.grid(row=0, column=0, sticky="ew")
        menubar.grid_columnconfigure(10, weight=1)

        # App mini-title in menu bar
        logo_pil = load_logo_image((22, 22))
        logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(22, 22))
        brand_lbl = ctk.CTkLabel(menubar, image=logo_ctk, text="  KeyFlow", compound="left", font=ctk.CTkFont(size=14, weight="bold"), text_color="#e2e8f0")
        brand_lbl.grid(row=0, column=0, padx=(14, 18), pady=8)

        menu_btn_style = {
            "width": 72,
            "height": 28,
            "corner_radius": 6,
            "fg_color": "transparent",
            "hover_color": "#1e293b",
            "text_color": "#cbd5e1",
            "font": ctk.CTkFont(size=13),
        }

        self.btn_file = ctk.CTkButton(menubar, text="File ▾", command=self._open_file_menu, **menu_btn_style)
        self.btn_file.grid(row=0, column=1, padx=2, pady=6)

        self.btn_view = ctk.CTkButton(menubar, text="View ▾", command=self._open_view_menu, **menu_btn_style)
        self.btn_view.grid(row=0, column=2, padx=2, pady=6)

        self.btn_settings = ctk.CTkButton(menubar, text="Settings ▾", command=self._open_settings_menu, **menu_btn_style)
        self.btn_settings.grid(row=0, column=3, padx=2, pady=6)

        self.btn_about = ctk.CTkButton(menubar, text="Build Info", width=86, height=28, corner_radius=6, fg_color="transparent", hover_color="#1e293b", text_color="#c084fc", font=ctk.CTkFont(size=13, weight="bold"), command=self.show_build_info_dialog)
        self.btn_about.grid(row=0, column=4, padx=2, pady=6)

        # Right side quick actions in menu bar
        tray_btn = ctk.CTkButton(
            menubar,
            text="Minimize to Tray",
            width=130,
            height=28,
            corner_radius=8,
            fg_color="#1e293b",
            hover_color="#334155",
            border_width=1,
            border_color="#475569",
            text_color="#f8fafc",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.hide_window,
        )
        tray_btn.grid(row=0, column=11, padx=(6, 14), pady=6)

    def _popup_menu(self, widget, items):
        menu = tk.Menu(self, tearoff=0, bg="#0f172a", fg="#f8fafc", activebackground="#9333ea", activeforeground="#ffffff", font=("Segoe UI", 10), bd=1, relief="solid")
        for item in items:
            if item == "---":
                menu.add_separator()
            else:
                label, cmd = item
                menu.add_command(label=f"  {label}  ", command=cmd)
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height()
        menu.tk_popup(x, y)

    def _open_file_menu(self):
        self._popup_menu(self.btn_file, [
            ("Open Web UI in Browser", lambda: webbrowser.open(f"{self.url}/?pin={self.pin}")),
            ("Copy Connection URL", self.copy_url),
            ("Copy 6-Digit PIN", self.copy_pin),
            "---",
            ("Minimize to System Tray (Ctrl+M)", self.hide_window),
            ("Exit Completely (Ctrl+Q)", self.quit_app),
        ])

    def _open_view_menu(self):
        top_state = "✓ " if self.always_on_top.get() else ""
        qr_label = "Switch to Compact QR" if self.qr_size_mode == "large" else "Switch to Large QR"
        self._popup_menu(self.btn_view, [
            (f"{top_state}Always on Top", self.toggle_always_on_top),
            (qr_label, self.toggle_qr_size),
            "---",
            ("Clear Activity Log", self.clear_logs),
            ("Refresh Network IP", self.refresh_network_info),
        ])

    def _open_settings_menu(self):
        tray_state = "✓ " if self.close_to_tray.get() else ""
        self._popup_menu(self.btn_settings, [
            ("Regenerate 6-Digit PIN", self.regenerate_pin),
            (f"{tray_state}Close Button Minimizes to Tray", self.toggle_close_behavior),
            "---",
            ("Reset Product Activation", self.reset_activation),
            ("Build & System Information", self.show_build_info_dialog),
        ])

    def _build_dashboard_body(self):
        body = ctk.CTkFrame(self, fg_color="#0b1120", corner_radius=0)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=4, minsize=340)  # Left column: QR & Pairing
        body.grid_columnconfigure(1, weight=6, minsize=420)  # Right column: Telemetry & Logs
        body.grid_rowconfigure(0, weight=1)

        # ==================== LEFT PANEL: PAIRING & QR ====================
        left_card = ctk.CTkFrame(body, fg_color="#131c31", corner_radius=18, border_width=1, border_color="#1e293b")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        left_card.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Phone Pairing", font=ctk.CTkFont(size=18, weight="bold"), text_color="#f8fafc").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(header_frame, text="Same Wi-Fi Network", font=ctk.CTkFont(size=12), text_color="#38bdf8").grid(row=0, column=1, sticky="e")

        # QR Code container
        qr_box = ctk.CTkFrame(left_card, fg_color="#ffffff", corner_radius=14)
        qr_box.grid(row=1, column=0, pady=8, padx=20)
        self.qr_label = ctk.CTkLabel(qr_box, text="")
        self.qr_label.pack(padx=10, pady=10)
        self._render_qr_code()

        # URL Box
        url_frame = ctk.CTkFrame(left_card, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#334155")
        url_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(8, 6))
        url_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(url_frame, text="SERVER URL", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").grid(row=0, column=0, sticky="w", padx=14, pady=(8, 0))
        self.url_lbl = ctk.CTkLabel(url_frame, text=self.url, font=ctk.CTkFont(family="Consolas", size=15, weight="bold"), text_color="#c084fc")
        self.url_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        self.copy_url_btn = ctk.CTkButton(url_frame, text="Copy", width=64, height=30, corner_radius=8, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=12, weight="bold"), command=self.copy_url)
        self.copy_url_btn.grid(row=0, column=1, rowspan=2, padx=10, pady=8)

        # PIN Code Box (Prominently visible, never cut off!)
        pin_frame = ctk.CTkFrame(left_card, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#334155")
        pin_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        pin_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pin_frame, text="SECURITY PIN CODE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").grid(row=0, column=0, sticky="w", padx=14, pady=(8, 0))
        self.pin_lbl = ctk.CTkLabel(pin_frame, text=self.pin, font=ctk.CTkFont(family="Consolas", size=26, weight="bold"), text_color="#34d399")
        self.pin_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        pin_btns = ctk.CTkFrame(pin_frame, fg_color="transparent")
        pin_btns.grid(row=0, column=1, rowspan=2, padx=10, pady=8)

        self.copy_pin_btn = ctk.CTkButton(pin_btns, text="Copy", width=60, height=28, corner_radius=8, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=12, weight="bold"), command=self.copy_pin)
        self.copy_pin_btn.pack(side="left", padx=(0, 6))

        ctk.CTkButton(pin_btns, text="New PIN", width=72, height=28, corner_radius=8, fg_color="#312e81", hover_color="#4338ca", font=ctk.CTkFont(size=12, weight="bold"), command=self.regenerate_pin).pack(side="left")

        ctk.CTkLabel(left_card, text="Scan QR with phone camera to auto-login", font=ctk.CTkFont(size=12), text_color="#94a3b8").grid(row=4, column=0, pady=(4, 12))

        # ==================== RIGHT PANEL: LIVE TELEMETRY & LOGS ====================
        right_col = ctk.CTkFrame(body, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_rowconfigure(0, weight=0)  # Live Status Card
        right_col.grid_rowconfigure(1, weight=1)  # Activity Log Card

        # --- Card 1: Live Typing Monitor & Controls ---
        monitor_card = ctk.CTkFrame(right_col, fg_color="#131c31", corner_radius=18, border_width=1, border_color="#1e293b")
        monitor_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        monitor_card.grid_columnconfigure((0, 1, 2), weight=1)

        mon_top = ctk.CTkFrame(monitor_card, fg_color="transparent")
        mon_top.grid(row=0, column=0, columnspan=3, sticky="ew", padx=20, pady=(16, 10))
        mon_top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(mon_top, text="Live Typing Monitor", font=ctk.CTkFont(size=18, weight="bold"), text_color="#f8fafc").grid(row=0, column=0, sticky="w")
        self.state_badge = ctk.CTkLabel(mon_top, text="  IDLE · READY  ", font=ctk.CTkFont(size=12, weight="bold"), fg_color="#1e293b", text_color="#38bdf8", corner_radius=8)
        self.state_badge.grid(row=0, column=1, sticky="e")

        # 3 Telemetry Stat Boxes
        stat1 = ctk.CTkFrame(monitor_card, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        stat1.grid(row=1, column=0, sticky="ew", padx=(20, 6), pady=6)
        ctk.CTkLabel(stat1, text="PROGRESS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.progress_lbl = ctk.CTkLabel(stat1, text="0 / 0 chars", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f8fafc")
        self.progress_lbl.pack(anchor="w", padx=12, pady=(2, 8))

        stat2 = ctk.CTkFrame(monitor_card, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        stat2.grid(row=1, column=1, sticky="ew", padx=6, pady=6)
        ctk.CTkLabel(stat2, text="ACTIVE MODE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.mode_lbl = ctk.CTkLabel(stat2, text="CODE (Auto-Indent)", font=ctk.CTkFont(size=15, weight="bold"), text_color="#c084fc")
        self.mode_lbl.pack(anchor="w", padx=12, pady=(2, 8))

        stat3 = ctk.CTkFrame(monitor_card, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#1e293b")
        stat3.grid(row=1, column=2, sticky="ew", padx=(6, 20), pady=6)
        ctk.CTkLabel(stat3, text="SPEED", font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(anchor="w", padx=12, pady=(8, 0))
        self.speed_lbl = ctk.CTkLabel(stat3, text="14 CPS (~168 WPM)", font=ctk.CTkFont(size=15, weight="bold"), text_color="#34d399")
        self.speed_lbl.pack(anchor="w", padx=12, pady=(2, 8))

        # Progress bar
        self.prog_bar = ctk.CTkProgressBar(monitor_card, height=10, corner_radius=5, fg_color="#0f172a", progress_color="#a855f7")
        self.prog_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=(8, 12))
        self.prog_bar.set(0)

        # PC Action Buttons
        ctrl_frame = ctk.CTkFrame(monitor_card, fg_color="transparent")
        ctrl_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=20, pady=(0, 16))
        ctrl_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.pause_btn = ctk.CTkButton(
            ctrl_frame,
            text="Pause / Resume (F9)",
            height=38,
            corner_radius=10,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=toggle_pause,
        )
        self.pause_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            ctrl_frame,
            text="Emergency Stop (F8)",
            height=38,
            corner_radius=10,
            fg_color="#be123c",
            hover_color="#9f1239",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: stop_evt.set(),
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=6)

        ctk.CTkButton(
            ctrl_frame,
            text="Open Web Controller",
            height=38,
            corner_radius=10,
            fg_color="#6d28d9",
            hover_color="#5b21b6",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: webbrowser.open(f"{self.url}/?pin={self.pin}"),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        # --- Card 2: Activity Log & Build Summary ---
        log_card = ctk.CTkFrame(right_col, fg_color="#131c31", corner_radius=18, border_width=1, border_color="#1e293b")
        log_card.grid(row=1, column=0, sticky="nsew")
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
        log_hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        log_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_hdr, text="Server Activity & Telemetry Log", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f8fafc").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(log_hdr, text="Clear Log", width=76, height=26, corner_radius=6, fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11), command=self.clear_logs).grid(row=0, column=1, sticky="e")

        self.log_box = ctk.CTkTextbox(log_card, fg_color="#090d16", text_color="#94a3b8", font=ctk.CTkFont(family="Consolas", size=12), corner_radius=12, border_width=1, border_color="#1e293b")
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=20, pady=(4, 16))
        self.log_box.configure(state="disabled")

    def _build_status_bar(self):
        statusbar = ctk.CTkFrame(self, height=32, corner_radius=0, fg_color="#090d16", border_width=1, border_color="#1e293b")
        statusbar.grid(row=2, column=0, sticky="ew")
        statusbar.grid_columnconfigure(1, weight=1)

        self.status_left = ctk.CTkLabel(
            statusbar,
            text=f"  ● Server Active on {self.url}   |   Host: {socket.gethostname()}",
            font=ctk.CTkFont(size=12),
            text_color="#34d399",
        )
        self.status_left.grid(row=0, column=0, padx=10, pady=4, sticky="w")

        self.status_right = ctk.CTkLabel(
            statusbar,
            text=f"Modes: Code / Shift+Enter / Enter   |   F8 Stop · F9 Pause   |   v{APP_VERSION} ({APP_BUILD})  ",
            font=ctk.CTkFont(size=12),
            text_color="#64748b",
        )
        self.status_right.grid(row=0, column=2, padx=10, pady=4, sticky="e")

    # -------------------- UI Actions & Helpers --------------------
    def _render_qr_code(self):
        qr = qrcode.QRCode(border=1, box_size=10)
        qr.add_data(f"{self.url}/?pin={self.pin}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").get_image()
        px = 230 if self.qr_size_mode == "large" else 185
        qr_ctk = ctk.CTkImage(light_image=img, dark_image=img, size=(px, px))
        self.qr_label.configure(image=qr_ctk)
        self.qr_label.image = qr_ctk

    def copy_url(self):
        self.clipboard_clear()
        self.clipboard_append(self.url)
        add_log(f"Copied server URL to clipboard: {self.url}")
        if hasattr(self, "copy_url_btn"):
            self.copy_url_btn.configure(text="Copied!")
            self.after(1500, lambda: self.copy_url_btn.configure(text="Copy"))

    def copy_pin(self):
        self.clipboard_clear()
        self.clipboard_append(self.pin)
        add_log("Copied 6-digit PIN code to clipboard.")
        if hasattr(self, "copy_pin_btn"):
            self.copy_pin_btn.configure(text="Copied!")
            self.after(1500, lambda: self.copy_pin_btn.configure(text="Copy"))

    def regenerate_pin(self):
        global PIN
        PIN = f"{secrets.randbelow(10**6):06d}"
        self.pin = PIN
        try:
            PIN_FILE.write_text(PIN)
        except Exception:
            pass
        if hasattr(self, "pin_lbl"):
            self.pin_lbl.configure(text=self.pin)
            self._render_qr_code()
        add_log(f"Generated new security PIN: {self.pin}")

    def toggle_always_on_top(self):
        val = not self.always_on_top.get()
        self.always_on_top.set(val)
        self.attributes("-topmost", val)
        add_log(f"Always on Top set to: {val}")

    def toggle_qr_size(self):
        self.qr_size_mode = "large" if self.qr_size_mode == "normal" else "normal"
        self._render_qr_code()

    def toggle_close_behavior(self):
        val = not self.close_to_tray.get()
        self.close_to_tray.set(val)
        add_log(f"Minimize to Tray on close set to: {val}")

    def refresh_network_info(self):
        self.url = f"http://{lan_ip()}:{PORT}"
        if hasattr(self, "url_lbl"):
            self.url_lbl.configure(text=self.url)
            self._render_qr_code()
        add_log(f"Refreshed network address: {self.url}")

    def clear_logs(self):
        event_logs.clear()
        self._last_log_len = 0
        if hasattr(self, "log_box"):
            self.log_box.configure(state="normal")
            self.log_box.delete("1.0", "end")
            self.log_box.configure(state="disabled")

    def reset_activation(self):
        try:
            if LICENSE_FILE.exists():
                LICENSE_FILE.unlink()
        except Exception:
            pass
        self.show_activation_screen()

    def show_build_info_dialog(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("KeyFlow — Build & System Info")
        dlg.geometry("480x400")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.configure(fg_color="#0f172a")

        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 480) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 400) // 2
        dlg.geometry(f"480x400+{max(0, x)}+{max(0, y)}")

        card = ctk.CTkFrame(dlg, fg_color="#1e293b", corner_radius=16, border_width=1, border_color="#334155")
        card.pack(fill="both", expand=True, padx=18, pady=18)

        ctk.CTkLabel(card, text=f"{APP_NAME} Desktop Server", font=ctk.CTkFont(size=20, weight="bold"), text_color="#f8fafc").pack(pady=(18, 2))
        ctk.CTkLabel(card, text=f"Version {APP_VERSION} · Build {APP_BUILD}", font=ctk.CTkFont(size=13, weight="bold"), text_color="#c084fc").pack(pady=(0, 14))

        info_lines = [
            ("Typing Engine", "Code-Aware Auto-Indent Engine v2.0"),
            ("Supported Modes", "Code / Shift+Enter / Enter (3-Mode)"),
            ("Host Machine", f"{socket.gethostname()} ({platform.system()} {platform.release()})"),
            ("Python Runtime", f"Python {platform.python_version()} ({platform.machine()})"),
            ("Local Endpoint", f"{self.url} (PIN Protected)"),
            ("Global Hotkeys", "F8 (Emergency Stop)  |  F9 (Pause/Resume)"),
            ("License Status", "Activated (SHA-256 Hardware/Key Verified)"),
        ]

        info_box = ctk.CTkFrame(card, fg_color="#0f172a", corner_radius=12)
        info_box.pack(fill="x", padx=18, pady=6)

        for k, v in info_lines:
            row = ctk.CTkFrame(info_box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=f"{k}:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8", width=130, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=v, font=ctk.CTkFont(size=12), text_color="#f8fafc", anchor="w").pack(side="left")

        ctk.CTkButton(card, text="Close", width=140, height=36, corner_radius=10, fg_color="#9333ea", hover_color="#7e22ce", font=ctk.CTkFont(size=13, weight="bold"), command=dlg.destroy).pack(pady=(14, 14))

    def _poll_ui_status(self):
        if not self.winfo_exists():
            return
        try:
            st = job["state"]
            typed = job["typed"]
            total = job["total"]
            cps = job["cps"]
            mode = job.get("mode", "code")

            if hasattr(self, "state_badge"):
                if st == "idle":
                    self.state_badge.configure(text="  IDLE · READY  ", fg_color="#1e293b", text_color="#38bdf8")
                elif st == "countdown":
                    self.state_badge.configure(text=f"  STARTING IN {job['countdown']}s  ", fg_color="#78350f", text_color="#fde047")
                elif st == "typing":
                    self.state_badge.configure(text="  ● TYPING LIVE  ", fg_color="#064e3b", text_color="#34d399")
                elif st == "paused":
                    self.state_badge.configure(text="  ❚❚ PAUSED  ", fg_color="#78350f", text_color="#fbbf24")
                elif st == "done":
                    self.state_badge.configure(text="  ✓ COMPLETED  ", fg_color="#1e1b4b", text_color="#c084fc")
                elif st == "stopped":
                    self.state_badge.configure(text="  ■ STOPPED  ", fg_color="#4c0519", text_color="#fb7185")

            if hasattr(self, "progress_lbl"):
                pct = int(round(100 * typed / total)) if total > 0 else 0
                self.progress_lbl.configure(text=f"{typed:,} / {total:,} ({pct}%)")
                self.prog_bar.set((typed / total) if total > 0 else 0)

            if hasattr(self, "mode_lbl"):
                mode_names = {
                    "code": "CODE (Auto-Indent)",
                    "shift": "SHIFT+ENTER (Chat)",
                    "enter": "ENTER (Standard)",
                }
                self.mode_lbl.configure(text=mode_names.get(mode, mode.upper()))

            if hasattr(self, "speed_lbl"):
                self.speed_lbl.configure(text=f"{int(cps)} CPS (~{int(cps * 12)} WPM)")

            if hasattr(self, "log_box") and len(event_logs) != self._last_log_len:
                self._last_log_len = len(event_logs)
                self.log_box.configure(state="normal")
                self.log_box.delete("1.0", "end")
                self.log_box.insert("end", "\n".join(event_logs) + "\n")
                self.log_box.see("end")
                self.log_box.configure(state="disabled")
        except Exception:
            pass

        self.after(250, self._poll_ui_status)


def main():
    try:
        ui = KeyFlowApp()
        ui.mainloop()
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(f"Failed to start GUI: {e}\n")


if __name__ == "__main__":
    main()
