bl_info = {'name': 'Codex Local Blender Bridge', 'author': 'Local workspace', 'version': (1, 0, 0), 'blender': (4, 0, 0), 'location': 'View3D > Sidebar > Codex', 'description': 'Local-only scene control on 127.0.0.1:9876', 'category': 'Development'}
import bpy, socket, threading, queue, json, traceback, io, contextlib
_jobs=queue.Queue()
_server=None
_alive=False
def _client(conn):
    try:
        conn.settimeout(300)
        data=b''
        while b'\n' not in data:
            chunk=conn.recv(65536)
            if not chunk:return
            data+=chunk
            if len(data)>4*1024*1024:raise ValueError('Request too large')
        req=json.loads(data.split(b'\n')[0]); done=threading.Event(); result={}
        _jobs.put((req,done,result))
        if not done.wait(290):result.update(ok=False,error='Main thread timeout')
        conn.sendall((json.dumps(result,ensure_ascii=False)+'\n').encode('utf-8'))
    except Exception as e:
        try:conn.sendall((json.dumps({'ok':False,'error':str(e)})+'\n').encode())
        except Exception:pass
    finally:conn.close()
def _listen():
    while _alive:
        try:
            conn,_=_server.accept(); threading.Thread(target=_client,args=(conn,),daemon=True).start()
        except socket.timeout:continue
        except OSError:break
def _tick():
    if not _alive:return None
    try:req,done,result=_jobs.get_nowait()
    except queue.Empty:return .1
    try:
        if req.get('op')=='status':
            result.update(ok=True,version=bpy.app.version_string,file=bpy.data.filepath,objects=len(bpy.data.objects),frame=bpy.context.scene.frame_current)
        elif req.get('op')=='execute':
            output=io.StringIO(); ns={'bpy':bpy,'__name__':'__main__'}
            with contextlib.redirect_stdout(output):exec(compile(req['code'],'<local-bridge>','exec'),ns)
            result.update(ok=True,output=output.getvalue(),result=ns.get('result'))
        else:raise ValueError('Unknown operation')
    except Exception:result.update(ok=False,error=traceback.format_exc())
    finally:done.set()
    return .1
def start():
    global _server,_alive
    if _alive:return
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    try:s.bind(('127.0.0.1',9876)); s.listen(4); s.settimeout(.5)
    except OSError as e:s.close(); print('Codex bridge:',e); return
    _server=s; _alive=True
    threading.Thread(target=_listen,daemon=True).start()
    bpy.app.timers.register(_tick,persistent=True)
def stop():
    global _alive,_server
    _alive=False
    if _server:_server.close(); _server=None
    if bpy.app.timers.is_registered(_tick):bpy.app.timers.unregister(_tick)
class CODEX_OT_bridge_start(bpy.types.Operator):
    bl_idname='codex_bridge.start'; bl_label='Connect local bridge'
    def execute(self,context):start(); return {'FINISHED'}
class CODEX_OT_bridge_stop(bpy.types.Operator):
    bl_idname='codex_bridge.stop'; bl_label='Disconnect'
    def execute(self,context):stop(); return {'FINISHED'}
class CODEX_PT_bridge(bpy.types.Panel):
    bl_label='Codex Local Connection'; bl_idname='CODEX_PT_bridge'; bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Codex'
    def draw(self,context):
        self.layout.label(text='Connected: 127.0.0.1:9876' if _alive else 'Disconnected')
        self.layout.operator('codex_bridge.stop' if _alive else 'codex_bridge.start')
classes=(CODEX_OT_bridge_start,CODEX_OT_bridge_stop,CODEX_PT_bridge)
def register():
    for cls in classes:bpy.utils.register_class(cls)
    if not bpy.app.background:start()
def unregister():
    stop()
    for cls in reversed(classes):bpy.utils.unregister_class(cls)
if __name__=='__main__':register()
