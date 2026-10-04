"""Isolated browser harness for the real extension; never loads user workflows.

Run with ComfyUI's Python, then open http://127.0.0.1:8766.
Preset writes use a temporary library that is removed on exit.
"""
import json
import sys
import tempfile
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from detailer_x.config import DEFAULTS, BUILTINS, CHOICES, RANGES
from detailer_x import presets

PAGE='''<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>DetailerX isolated UI test</title></head>
<body style="background:#171a21;color:white;font:14px system-ui;margin:12px"><h1>DetailerX isolated UI test</h1><p>Real extension, isolated graph and temporary preset library.</p>
<button onclick="window.dxNode.setSize([520,900])">Minimum width</button><button onclick="window.dxNode.setSize([850,900])">Expanded width</button><button onclick="window.copyNode()">Duplicate saved node</button>
<main id="nodes" style="display:flex;flex-wrap:wrap;gap:24px;margin-top:16px"></main>
<script type="module">import '/web/js/detailer_x.js';</script></body></html>'''
APP='''let ext,nextId=1; export const app={graph:{id:'entry-preview',change(){}},registerExtension(e){ext=e;start();},async graphToPrompt(){return {workflow:{},output:{[window.dxNode.id]:{class_type:'WorkflowX_DetailerX',inputs:{settings:window.dxNode.widgets[0].serializeValue()}}}}}};
class Node{constructor(){this.id=nextId++;this.graph=app.graph;this.widgets=[{name:'settings',value:'{}',inputEl:{style:{}}}];this.properties={};this.inputs=Array(6);this.outputs=Array(9);this.size=[520,950];this.onNodeCreated();}
setDirtyCanvas(){} setSize(size){this.size=size;if(this.host){this.host.style.width=size[0]+'px';this.host.style.height=(size[1]-220)+'px';}}
addDOMWidget(name,type,element,options){this.host=element;document.querySelector('#nodes').append(element);const w={name,type,element,options};this.widgets.push(w);return w;}}
async function start(){await ext.beforeRegisterNodeDef(Node,{name:'WorkflowX_DetailerX'});window.dxNode=new Node();window.copyNode=()=>{const data={};window.dxNode.onSerialize(data);const copy=new Node();copy.onConfigure(JSON.parse(JSON.stringify(data)));window.dxCopy=copy;};}'''
API='''export const api={fetchApi:(url,options)=>fetch(url,options),addEventListener(){}};'''

def main():
    with tempfile.TemporaryDirectory(prefix="detailerx-ui-") as temporary:
        path=Path(temporary)/"presets.json"
        sessions={}
        class Handler(BaseHTTPRequestHandler):
            def reply(self,data,kind="application/json",status=200):
                body=data.encode() if isinstance(data,str) else json.dumps(data).encode()
                self.send_response(status);self.send_header("Content-Type",kind);self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(body)
            def do_GET(self):
                route=self.path.split("?")[0]
                if route=="/workflowx_configurator/detailer_x/entry":
                    from urllib.parse import parse_qs,urlsplit
                    owner=parse_qs(urlsplit(self.path).query).get("owner",[""])[0]
                    sessions.setdefault(owner,dict(token="preview",owner=owner,state="paused",remaining=300,can_rerun=False,batch=2,revision=0))
                    return self.reply(sessions[owner])
                if route=="/workflowx_configurator/detailer_x/entry/image":
                    return self.reply('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect width="640" height="480" fill="#283f65"/><circle cx="320" cy="240" r="140" fill="#a4bee7"/><text x="160" y="440" fill="white" font-size="26">Synthetic input preview</text></svg>',"image/svg+xml")
                if route=="/":return self.reply(PAGE,"text/html")
                if route=="/scripts/app.js":return self.reply(APP,"text/javascript")
                if route=="/scripts/api.js":return self.reply(API,"text/javascript")
                if route=="/workflowx_configurator/detailer_x/config":
                    return self.reply(dict(defaults=DEFAULTS,entry_controls=True,builtins=list(BUILTINS.values()),presets=list(presets.library(path).values()),choices=CHOICES,ranges=RANGES,
                        samplers=["euler","dpmpp_2m","res_multistep"],schedulers=["simple","beta","karras","flux2","krea2"],
                        assets={k:[] for k in ("upscale_models","sams","ultralytics","luts","neural_grain")}))
                if route in ("/web/js/detailer_x.js","/web/js/detailer_x_state.mjs","/web/js/detailer_x_help.mjs"):
                    return self.reply((ROOT/route.lstrip("/")).read_text("utf-8"),"text/javascript")
                self.reply({},status=404)
            def do_POST(self):
                if self.path=="/workflowx_configurator/detailer_x/entry":
                    data=json.loads(self.rfile.read(int(self.headers["Content-Length"])));s=sessions[data["owner"]]
                    if data["action"] in ("cancel","skip","resume"):
                        s.update(state="completed" if data["action"]=="resume" else "passed",can_rerun=True)
                    if data["action"]=="update":s["revision"]=data["revision"]
                    if data["action"]=="arm_skip":s["skip"]=data["enabled"]
                    return self.reply(s)
                if self.path=="/workflowx_configurator/detailer_x/rerun":
                    self.rfile.read(int(self.headers["Content-Length"]))
                    return self.reply(dict(prompt_id="isolated-preview"))
                if self.path!="/workflowx_configurator/detailer_x/presets":return self.reply({},status=404)
                try:
                    data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    self.reply(presets.save(data["preset"],data.get("expected_revision"),path))
                except Exception as exc:self.reply({"error":str(exc)},status=400)
        print("DetailerX preview: http://127.0.0.1:8766",flush=True)
        HTTPServer(("127.0.0.1",8766),Handler).serve_forever()

if __name__=="__main__":main()
