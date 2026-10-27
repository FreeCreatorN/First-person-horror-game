"""Connect only to the user's HorrorGame editor; never opens or closes a world."""
import sys,time,json
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,r'D:\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python')
import remote_execution as ue
out=Path(__file__).resolve().parent
script=sys.argv[1] if len(sys.argv)>1 else 'probe'
assert script in ('probe','inspect_legacy.py','import_set.py','show_assets.py')
report={'success':False,'script':script,'started_utc':datetime.now(timezone.utc).isoformat()}
s=ue.RemoteExecution()
try:
 s.start()
 for i in range(25):
  nodes=s.remote_nodes
  if nodes:break
  time.sleep(.2)
 report['nodes']=nodes
 if script=='probe':
  print(json.dumps(nodes,ensure_ascii=False));report['success']=bool(nodes)
 else:
  matches=[n for n in nodes if str(n.get('project_name','')).lower()=='horrorgame']
  assert len(matches)==1,('Need exactly one HorrorGame editor',nodes)
  s.open_command_connection(matches[0]['node_id'])
  path=out/script
  command='from pathlib import Path\nexec(compile(Path('+repr(str(path))+').read_text(encoding="utf-8-sig"), '+repr(str(path))+', "exec"), {"__name__":"__main__","__file__":'+repr(str(path))+'})'
  result=s.run_command(command,unattended=True,exec_mode=ue.MODE_EXEC_FILE)
  report['remote_result']=result
  assert result['success'],result
  if script!='show_assets.py':
   filename={'inspect_legacy.py':'legacy_inspection_report.json','import_set.py':'ue_import_report.json'}[script]
   task=json.loads((out/filename).read_text(encoding='utf-8-sig'))
   assert task['success'],task.get('error')
  report['success']=True
  print('UE_REMOTE_TASK_SUCCESS '+script)
except Exception as error:
 report['error']=repr(error);raise
finally:
 report['completed_utc']=datetime.now(timezone.utc).isoformat()
 (out/('remote_'+script.replace('.py','')+'_completion.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 s.stop()
