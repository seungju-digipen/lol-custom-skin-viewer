from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse,parse_qs,unquote
import zipfile,struct,json,subprocess,os,re,uuid,threading,io,shutil,traceback
from email.parser import BytesParser
from email.policy import default as email_policy
from PIL import Image
ROOT=Path(__file__).resolve().parent
CONFIG_PATH=ROOT/'config.json'
CONFIG=json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig')) if CONFIG_PATH.is_file() else {}
WORK=ROOT/'tools'
JOBS=ROOT/'.data/jobs'
JOBS.mkdir(parents=True,exist_ok=True)
GAME=Path(os.environ.get('LOL_CHAMPIONS_DIR') or CONFIG.get('champions_dir',r'C:\Riot Games\League of Legends\Game\DATA\FINAL\Champions'))
WAD=WORK/'wadtools/wadtools.exe'; CONVERTER=WORK/'lol2gltf.exe'
TEX=WORK/'ltk-tex-utils.exe'; RITOBIN=WORK/'ritobin/bin/ritobin_cli.exe'
STATE={}; LOCK=threading.Lock()
def update(key,**values):
 with LOCK: STATE[key].update(values)
def run(args,timeout=180):
 env=os.environ.copy(); env['DOTNET_ROOT']=str(WORK/'dotnet')
 p=subprocess.run([str(x) for x in args],capture_output=True,timeout=timeout,env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if p.returncode: raise ValueError((p.stderr+p.stdout).decode('utf-8',errors='replace')[-2200:])
def unpack(src,dest):
 with zipfile.ZipFile(src) as z:
  if sum(x.file_size for x in z.infolist())>1024*1024*1024: raise ValueError('압축 해제 용량이 1GB를 넘습니다.')
  for info in z.infolist():
   name=info.filename.replace('\\','/'); target=(dest/name).resolve()
   if not target.is_relative_to(dest.resolve()) or ':' in name: raise ValueError('안전하지 않은 압축 경로입니다.')
   if info.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
   target.parent.mkdir(parents=True,exist_ok=True)
   with z.open(info) as a,target.open('wb') as b: shutil.copyfileobj(a,b)
def merge_tree(src,dst):
 for f in src.rglob('*'):
  if f.is_file():
   t=dst/f.relative_to(src); t.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(f,t)
def glb_read(p):
 b=p.read_bytes(); n=struct.unpack_from('<I',b,12)[0]; d=json.loads(b[20:20+n]); pos=20+n; sz=struct.unpack_from('<I',b,pos)[0]; return d,b[pos+8:pos+8+sz]
def nodes(obj):
 if isinstance(obj,dict):
  yield obj
  for v in obj.values(): yield from nodes(v)
 elif isinstance(obj,list):
  for v in obj: yield from nodes(v)
def fields(node):
 return {str(x.get('key','')).lower():x.get('value') for x in node.get('items',[]) if isinstance(x,dict)}
def material_info(skin):
 job=skin
 while job.parent!=JOBS: job=job.parent
 skinname=skin.name.lower(); champion=skin.parent.parent.name.lower()
 skinid='0' if skinname=='base' else re.sub(r'^skin','',skinname)
 wanted='skin'+skinid+'.bin'; mapping={};default=None;hidden=[];warnings=[]
 candidates=[]
 for source in ('original','mod'):
  for f in (job/source).rglob('*.bin'):
   if f.name.lower()==wanted and ('characters/'+champion+'/') in f.as_posix().lower(): candidates.append(f)
 for i,f in enumerate(candidates):
  out=job/('materials-'+str(i)+'.json')
  try:
   run([RITOBIN,'-o','json',f,out])
   doc=json.loads(out.read_text(encoding='utf-8-sig'))
   for n in nodes(doc):
    if str(n.get('name','')).lower()=='skinmeshdataproperties':
     props=fields(n)
     if props.get('texture'): default=props['texture']
     hidden=[x.strip().lower() for x in str(props.get('initialsubmeshtohide','')).split(',') if x.strip()]
     for ov in nodes(props.get('materialoverride',{})):
      kv=fields(ov)
      if kv.get('submesh') and kv.get('texture'):mapping[str(kv['submesh']).lower()]=kv['texture']
  except Exception as e: warnings.append('BIN 재질 정보 읽기 실패: '+f.name)
 return mapping,default,hidden,warnings

def add_textures(path,skin):
 d,b=glb_read(path);mapping,default,hidden,warnings=material_info(skin)
 job=skin
 while job.parent!=JOBS: job=job.parent
 mod_textures={}
 for f in (job/'mod').rglob('*'):
  if f.is_file() and f.suffix.lower() in ('.dds','.tex','.png'):
   match=re.search(r'(assets/.*)',f.as_posix(),re.I)
   if match:mod_textures[match.group(1).lower().rsplit('.',1)[0]]=f
 textures=[x for x in skin.rglob('*') if x.suffix.lower() in ('.dds','.png','.tex') and 'particles' not in x.as_posix().lower()]
 root=job/'merged'; all_files={x.relative_to(root).as_posix().lower():x for x in root.rglob('*') if x.is_file()}
 d['images']=[];d['textures']=[];cache={};mapped=[]
 for mat in d.get('materials',[]):
  name=mat.get('name','').lower();ref=mapping.get(name,default); candidate=None
  if ref:
   normalized=str(ref).replace('\\','/').lower();candidate=mod_textures.get(normalized.rsplit('.',1)[0]) or all_files.get(normalized)
   if candidate is None:
    # Mods frequently store a DDS replacement for a TEX resource.
    candidate=next((x for k,x in all_files.items() if k.rsplit('.',1)[0]==normalized.rsplit('.',1)[0] and x.suffix.lower() in ('.dds','.tex','.png')),None)
  exact=candidate is not None
  if candidate is None:
   ranked=sorted(textures,key=lambda x:(0 if name and name in x.stem.lower() else 1,0 if ('weapon' in name)==('weapon' in x.stem.lower()) else 1,0 if 'tx_cm' in x.stem.lower() or 'diffuse' in x.stem.lower() else 1,x.name))
  else: ranked=[candidate]
  attached=False
  for f in ranked:
   try:
    if f not in cache:
     if f.suffix.lower()=='.tex':
      converted=job/'converted-textures'/(str(len(cache))+'.png');converted.parent.mkdir(exist_ok=True)
      run([TEX,'decode',f,'-o',converted]);image_file=converted
     else:image_file=f
     im=Image.open(image_file).convert('RGBA');png=io.BytesIO();im.save(png,format='PNG');data=png.getvalue()
     b+=b'\0'*((-len(b))%4);offset=len(b);b+=data
     vi=len(d['bufferViews']);d['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(data)})
     ti=len(d['textures']);d['images'].append({'bufferView':vi,'mimeType':'image/png'});d['textures'].append({'source':len(d['images'])-1});cache[f]=ti
    mat['pbrMetallicRoughness']={'baseColorTexture':{'index':cache[f]},'metallicFactor':0,'roughnessFactor':0.8};mat['doubleSided']=True
    if not exact:warnings.append('BIN 연결 정보 없음·파일명으로 추정: '+name)
    mapped.append({'material':name,'texture':f.name,'source':('mod-bin' if f in mod_textures.values() else 'original-bin') if exact else 'filename'})
    attached=True;break
   except Exception as e:
    if exact:warnings.append('텍스처 변환 실패: '+f.name+' / '+str(e)[:180])
  if not attached:warnings.append('텍스처를 읽지 못한 재질: '+name)
 # Initial mesh visibility from the game's skin definition.
 for mesh in d.get('meshes',[]):
  mesh['primitives']=[pr for pr in mesh['primitives'] if d['materials'][pr.get('material',0)].get('name','').lower() not in hidden]
 b+=b'\0'*((-len(b))%4);d['buffers'][0]['byteLength']=len(b);j=json.dumps(d,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
 path.write_bytes(struct.pack('<III',0x46546c67,2,28+len(j)+len(b))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b)
 (job/'texture-report.json').write_text(json.dumps(mapped,ensure_ascii=False,indent=2),encoding='utf-8')
 return [a.get('name','') for a in d.get('animations',[])],warnings

def process(key):
 job=JOBS/key;mod=job/'mod'; original=job/'original'; merged=job/'merged'
 try:
  update(key,message='모드 압축 해제 중')
  if (job/'upload.zip').is_file(): unpack(job/'upload.zip',mod)
  # Nested downloaded ZIPs are wrappers, not model files.
  if not list(mod.rglob('*.skn')) and not list(mod.rglob('*.wad.client')):
   nested=list(mod.rglob('*.fantome'))+list(mod.rglob('*.zip'))
   if len(nested)==1: unpack(nested[0],mod/'nested')
  update(key,message='모드 WAD에서 모델 추출 중')
  for i,wad in enumerate(f for f in mod.rglob('*.wad.client') if f.is_file()):
   if i>=20: raise ValueError('WAD 파일이 너무 많습니다.')
   run([WAD,'--hashtable-dir',WORK/'hashes','extract','-i',wad,'-o',mod/('wad-'+str(i)),'-x',r'(assets/characters/.*/skins/.*\.(skn|skl|anm|dds|tex)$|data/characters/.*/skins/skin[0-9]+\.bin$)'])
  models=sorted(mod.rglob('*.skn'))
  if not models: raise ValueError('챔피언 .skn 모델을 찾지 못했습니다. 감정표현·음성·맵 모드는 3D 스킨 뷰어 대상이 아닙니다.')
  choices=[]
  for f in models:
   match=re.search(r'characters/([^/]+)/skins/([^/]+)/',f.as_posix(),re.I)
   if match: choices.append((f,match.group(1),match.group(2)))
  if not choices: raise ValueError('모델은 있지만 챔피언/스킨 경로를 판별하지 못했습니다. assets/characters/... 경로가 필요합니다.')
  model,champ,skin=choices[0]
  if not re.fullmatch(r'[A-Za-z0-9_]+',champ+skin): raise ValueError('챔피언 경로가 올바르지 않습니다.')
  update(key,message=champ+' 원본 애니메이션 추출 중',champion=champ,skin=skin)
  wad=next((p for p in GAME.glob('*.wad.client') if p.name.lower()==champ.lower()+'.wad.client'),None)
  if not wad: raise ValueError('롤 설치 폴더에 '+champ+'.wad.client 파일이 없습니다.')
  skinid='0' if skin.lower()=='base' else re.sub(r'^skin','',skin,flags=re.I)
  pattern=r'(assets/characters/'+re.escape(champ)+r'/skins/'+re.escape(skin)+r'/.*\.(anm|skl|dds|tex)$|data/characters/'+re.escape(champ)+r'/skins/skin'+re.escape(skinid)+r'\.bin$)'
  run([WAD,'--hashtable-dir',WORK/'hashes','extract','-i',wad,'-o',original,'-x',pattern])
  merge_tree(original,merged)
  # Only copy the selected character/skin; override original files with mod assets.
  skinroot=model.parent
  while skinroot.name.lower()!=skin.lower() and skinroot!=mod: skinroot=skinroot.parent
  if skinroot==mod: raise ValueError('스킨 루트 폴더를 찾지 못했습니다.')
  target=merged/'assets/characters'/champ/'skins'/skin;target.mkdir(parents=True,exist_ok=True)
  merge_tree(skinroot,target)
  mesh=target/model.relative_to(skinroot)
  skeleton=mesh.with_suffix('.skl')
  if not skeleton.is_file():
   candidates=list(target.rglob('*.skl'))
   if len(candidates)!=1:raise ValueError('모델과 대응하는 뼈대를 확정하지 못했습니다. '+mesh.name)
   skeleton=candidates[0]
  if not skeleton: raise ValueError('원본과 모드에 .skl 뼈대 파일이 없습니다.')
  animations=job/'animations';animations.mkdir(exist_ok=True)
  for f in target.rglob('*.anm'): shutil.copy2(f,animations/f.name)
  update(key,message='모델·애니메이션 변환 중')
  result=job/'model.glb'
  args=[CONVERTER,'skn2gltf','-m',mesh,'-s',skeleton,'-g',result]
  if list(animations.iterdir()): args+=['-a',animations]
  run(args)
  names,warnings=add_textures(result,target)
  if len(choices)>1: warnings.append('모델 '+str(len(choices))+'개 중 첫 모델만 표시: '+model.name)
  warnings.append('스킬 이펙트·음성·게임 셰이더는 미포함. 원본 애니메이션과 커스텀 뼈대가 맞지 않으면 동작이 깨질 수 있습니다.')
  if (skinroot/model.relative_to(skinroot).with_suffix('.skl')).is_file():warnings.append('커스텀 뼈대를 사용합니다. 원본 애니메이션과의 호환성은 별도 확인이 필요합니다.')
  update(key,status='done',message='완료',model='/model/'+key,animations=names,warnings=warnings)
  (job/'result.json').write_text(json.dumps(STATE[key],ensure_ascii=False),encoding='utf-8')
 except Exception as e:
  update(key,status='error',message=str(e));traceback.print_exc()

LIBRARIES=ROOT/'.data/libraries'
LIBRARIES.mkdir(exist_ok=True)
def library_path(key):
 if not re.fullmatch('[0-9a-f]{32}',key):raise ValueError('잘못된 라이브러리 ID')
 return LIBRARIES/key
def catalog(key):
 root=library_path(key)/'files';items=[];seen=set()
 for meta in root.rglob('info.json'):
  if meta.parent.name.lower()!='meta':continue
  folder=meta.parent.parent
  try:name=json.loads(meta.read_text(encoding='utf-8-sig')).get('Name',folder.name)
  except Exception:name=folder.name
  rel=folder.relative_to(root).as_posix();items.append({'name':name,'path':rel,'kind':'folder'});seen.add(folder.name.lower())
 for f in root.rglob('*'):
  if not f.is_file() or f.suffix.lower() not in ('.zip','.fantome'):continue
  if f.stem.lower() in seen:continue
  if any(parent.name.lower() in ('raw','wad') for parent in f.parents):continue
  if any((parent/'META/info.json').is_file() for parent in f.parents if parent!=root.parent):continue
  items.append({'name':f.stem,'path':f.relative_to(root).as_posix(),'kind':'archive'})
 if not items and list(root.rglob('*.skn')):items=[{'name':'업로드한 폴더','path':'.','kind':'folder'}]
 result={'id':key,'items':sorted(items,key=lambda x:x['name'].lower())}
 (library_path(key)/'catalog.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');return result

def open_item(key,index):
 cat=json.loads((library_path(key)/'catalog.json').read_text(encoding='utf-8'))
 item=cat['items'][index];root=library_path(key)/'files';source=(root/item['path']).resolve()
 if not source.is_relative_to(root.resolve()):raise ValueError('잘못된 모드 경로')
 cached=item.get('job')
 if cached and (JOBS/cached/'model.glb').is_file():
  report=json.loads((JOBS/cached/'result.json').read_text(encoding='utf-8'))
  with LOCK:STATE[cached]=report
  return cached
 jobid=uuid.uuid4().hex;job=JOBS/jobid;job.mkdir()
 if item['kind']=='archive':shutil.copy2(source,job/'upload.zip')
 else:shutil.copytree(source,job/'mod')
 with LOCK:STATE[jobid]={'status':'working','message':'모드 준비 중'}
 item['job']=jobid;(library_path(key)/'catalog.json').write_text(json.dumps(cat,ensure_ascii=False),encoding='utf-8')
 threading.Thread(target=process,args=(jobid,),daemon=True).start();return jobid

class Handler(BaseHTTPRequestHandler):
 def send(self,data,kind='application/json',status=200):
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
 def json(self,value,status=200): self.send(json.dumps(value,ensure_ascii=False).encode(),'application/json; charset=utf-8',status)
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/libraries':
   return self.json([json.loads(f.read_text(encoding='utf-8')) for f in LIBRARIES.glob('*/catalog.json')])
  if path=='/': return self.send((ROOT/'index.html').read_bytes(),'text/html; charset=utf-8')
  if path.startswith('/status/'):
   key=path.rsplit('/',1)[-1]
   with LOCK: state=dict(STATE.get(key,{'status':'error','message':'작업 없음'}))
   return self.json(state)
  if path.startswith('/model/'):
   key=path.rsplit('/',1)[-1]
   if re.fullmatch('[0-9a-f]{32}',key) and (JOBS/key/'model.glb').is_file():
    file=JOBS/key/'model.glb'
    if parse_qs(urlparse(self.path).query).get('pose')==['bind']:
     d,b=glb_read(file);d.pop('animations',None);j=json.dumps(d,separators=(',',':')).encode();j+=b' '*((-len(j))%4)
     data=struct.pack('<III',0x46546c67,2,28+len(j)+len(b))+struct.pack('<II',len(j),0x4e4f534a)+j+struct.pack('<II',len(b),0x004e4942)+b
     return self.send(data,'model/gltf-binary')
    return self.send(file.read_bytes(),'model/gltf-binary')
  self.json({'error':'Not found'},404)
 def do_PUT(self):
  try:
   if self.headers.get('Origin','') not in ('','http://127.0.0.1:8766','http://localhost:8766'):raise ValueError('Origin rejected')
   parsed=urlparse(self.path);key=parsed.path.rsplit('/',1)[-1];root=library_path(key)/'files'
   if not root.is_dir():raise ValueError('라이브러리가 없습니다.')
   rel=parse_qs(parsed.query).get('path',[''])[0].replace('\\','/')
   target=(root/rel).resolve()
   if not rel or ':' in rel or not target.is_relative_to(root.resolve()):raise ValueError('잘못된 파일 경로')
   size=int(self.headers.get('Content-Length','0'))
   if size<0 or size>300*1024*1024:raise ValueError('개별 파일은 최대 300MB입니다.')
   target.parent.mkdir(parents=True,exist_ok=True)
   with target.open('wb') as f:
    remaining=size
    while remaining:
     chunk=self.rfile.read(min(remaining,1024*1024))
     if not chunk:raise ValueError('업로드 중단')
     f.write(chunk);remaining-=len(chunk)
   self.json({'ok':True})
  except Exception as e:self.json({'error':str(e)},400)
 def do_POST(self):
  if self.path.startswith('/library/'):
   try:
    if self.headers.get('Origin','') not in ('','http://127.0.0.1:8766','http://localhost:8766'):raise ValueError('Origin rejected')
    parts=self.path.strip('/').split('/')
    if parts==['library','create']:
     key=uuid.uuid4().hex;(library_path(key)/'files').mkdir(parents=True);return self.json({'id':key})
    if len(parts)==3 and parts[1]=='finish':return self.json(catalog(parts[2]))
    if len(parts)==4 and parts[1]=='open':return self.json({'id':open_item(parts[2],int(parts[3]))})
    raise ValueError('지원하지 않는 요청')
   except Exception as e:return self.json({'error':str(e)},400)
  if self.path not in ('/upload','/upload-folder'): return self.json({'error':'Not found'},404)
  origin=self.headers.get('Origin','')
  if origin and origin not in ('http://127.0.0.1:8766','http://localhost:8766'): return self.json({'error':'Origin rejected'},403)
  try: size=int(self.headers.get('Content-Length','0'))
  except ValueError: size=0
  if size<=0 or size>300*1024*1024:return self.json({'error':'파일 크기는 최대 300MB입니다.'},400)
  key=uuid.uuid4().hex;job=JOBS/key;job.mkdir()
  try:
   if self.path=='/upload-folder':
    content_type=self.headers.get('Content-Type','')
    if not content_type.lower().startswith('multipart/form-data;'):raise ValueError('폴더 업로드 형식이 올바르지 않습니다.')
    raw=self.rfile.read(size)
    if len(raw)!=size:raise ValueError('폴더 업로드가 중단되었습니다.')
    multipart=BytesParser(policy=email_policy).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
    mod=job/'mod';mod.mkdir();count=0
    for part in multipart.iter_parts():
     filename=part.get_filename()
     if not filename:continue
     name=filename.replace('\\','/');dest=(mod/name).resolve()
     if not dest.is_relative_to(mod.resolve()) or ':' in name:raise ValueError('안전하지 않은 파일 경로입니다.')
     if count>=10000:raise ValueError('폴더의 파일은 최대 10,000개입니다.')
     dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(part.get_payload(decode=True) or b'');count+=1
    if not count:raise ValueError('폴더 안에 파일이 없습니다.')
    with LOCK:STATE[key]={'status':'working','message':'폴더 업로드 완료: '+str(count)+'개'}
    threading.Thread(target=process,args=(key,),daemon=True).start();return self.json({'id':key})
   with (job/'upload.zip').open('wb') as f:
    remaining=size
    while remaining:
     chunk=self.rfile.read(min(remaining,1024*1024))
     if not chunk: raise ValueError('업로드가 중단되었습니다.')
     f.write(chunk);remaining-=len(chunk)
   if not zipfile.is_zipfile(job/'upload.zip'): return self.json({'error':'ZIP 또는 FANTOME 파일을 선택해주세요.'},400)
   with LOCK: STATE[key]={'status':'working','message':'업로드 완료'}
   threading.Thread(target=process,args=(key,),daemon=True).start();self.json({'id':key})
  except Exception as e: self.json({'error':str(e)},400)
if __name__=='__main__':
 print('Skin viewer: http://127.0.0.1:8766/',flush=True)
 ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
